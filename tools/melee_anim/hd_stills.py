"""Native single-frame PNGs; evaluate full framing without rasterizing a clip."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile
import threading
import time
import uuid

from PIL import Image
from .rotations import RotationCache
from .export_progress import render_progress

HD_SIZES = (2048, 4096)
HD_DEFAULT_SIZE = 4096


def crop_transparent_png(source, source_key):
    """Trim only alpha-zero pixels after native rendering; never resize content."""
    source=Path(source)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    key=hashlib.sha256(('alpha-bounds-v1:'+source_key+':'+digest).encode()).hexdigest()
    target=source.parent/'cropped.png';marker=source.parent/'crop.json'
    if target.is_file() and marker.is_file():
        try:
            saved=json.loads(marker.read_text())
            if saved['key']==key and saved['sha256']==hashlib.sha256(target.read_bytes()).hexdigest():
                return target,key
        except (ValueError,KeyError,OSError,TypeError):pass
    with Image.open(source) as image:
        if image.mode!='RGBA':raise ValueError('HD cropping requires an RGBA PNG')
        # Alpha1 counts as visible; black RGB is never treated as transparency.
        bounds=image.getchannel('A').getbbox()
        cropped=image.crop(bounds or (0,0,1,1))
        temporary=target.with_suffix('.png.tmp')
        cropped.save(temporary,format='PNG')
        temporary.replace(target)
        saved={'key':key,'source_size':list(image.size),'bounds':list(bounds) if bounds else None,
               'output_size':list(cropped.size),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    temporary=marker.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(saved,indent=2)+'\n');temporary.replace(marker)
    return target,key


class HDArtifacts:
    """Short-lived downloads in OS temporary storage, outside the project."""
    def __init__(self, ttl=600):
        self.ttl, self.active = ttl, 0
        self.lock, self.stop = threading.RLock(), threading.Event()
        self.records, self.temp, self.thread = {}, None, None

    @property
    def root(self):
        with self.lock:
            if self.temp is None:
                self.temp = tempfile.TemporaryDirectory(prefix='melee-hd-',ignore_cleanup_errors=True)
                self.thread = threading.Thread(target=self._maintain, daemon=True)
                self.thread.start()
            return Path(self.temp.name).resolve()

    def _maintain(self):
        while not self.stop.wait(60):self.prune()

    def begin(self):
        with self.lock:self.active += 1

    def end(self):
        with self.lock:self.active -= 1

    def publish(self, path, filename):
        path = Path(path).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ValueError('Unknown HD artifact')
        with self.lock:
            token = uuid.uuid4().hex+path.suffix
            self.records[token] = (path, filename, time.monotonic()+self.ttl)
            os.utime(path.parent, None)
            return '/hd-export/'+token

    def get(self, token):
        with self.lock:
            row = self.records.get(token)
            if row is None or row[2] < time.monotonic():return None
            return row[:2]

    def prune(self):
        with self.lock:
            if self.active or self.temp is None:return
            self.records = {k:v for k,v in self.records.items() if v[2] >= time.monotonic()}
            retained = {row[0].parent for row in self.records.values()}
            root = self.root
            for parent in ('renders', 'bundles'):
                for folder in (root/parent).glob('*'):
                    if folder in retained or time.time()-folder.stat().st_mtime < self.ttl:continue
                    target = folder.resolve()
                    if not target.is_relative_to(root):raise RuntimeError('Unexpected HD cleanup path')
                    try:shutil.rmtree(target)
                    except OSError:pass  # An in-flight browser download may still hold a file.

    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(timeout=2)
        if self.temp:self.temp.cleanup()


class StillCache(RotationCache):
    def __init__(self, root, output_root, repo=None):
        super().__init__(root, repo)
        self.output_root = Path(output_root).resolve()

    def selection(self, clip, frame, cycle):
        if clip.get('lazy'):
            from .attacks import sample_times
            manifest = {'sample_source_times': sample_times(clip['period'], clip['authored_loop'], clip['fps']),
                        'fps': clip['fps']}
        else:
            original = self.root/Path(clip['gif']).parent/'preview-manifest.json'
            manifest = json.loads(original.read_text())
        selected = manifest
        if cycle == 'sync':
            selected = json.loads((self.root/Path(clip['sync_cycle']['gif']).parent/'preview-manifest.json').read_text())
        short = ((clip.get('dirty_cycle') if cycle == 'dirty' else None) or clip.get('minimum_cycle')) if cycle in ('minimum', 'dirty') and clip['action_key'] == 'results-clap_source' else None
        length = short['length'] if short else len(selected['sample_source_times'])
        if not isinstance(frame, int) or not 0 <= frame < length:
            raise ValueError('Frame index is outside this animation')
        return manifest, (short['start'] if short else 0)+frame

    def get(self, clip, angles, size, frame=0, cycle='full', power='none', center=False,
            effects=False, electric=True, progress=None):
        if size not in HD_SIZES:
            raise ValueError('HD PNG size must be 2048 or 4096')
        with self.lock:
            manifest, sample_index = self.selection(clip, frame, cycle)
            manifest = {**manifest, 'ground_effects_enabled': effects, 'judge_electric': electric}
            resource_key, settings, model, companion = self._inputs(
                clip, angles, cycle == 'sync', power, center, manifest_override=manifest)
            settings = {**settings, 'version': 'hd-png-v1', 'size': size, 'selected_sample_index': sample_index,
                        'resource_key': resource_key}
            key = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()
            folder = self.output_root/key
            marker = folder/'complete.json'
            names = ('frame_0000.png', 'preview-manifest.json')
            ready = False
            if marker.is_file():
                try:
                    saved = json.loads(marker.read_text())
                    ready = saved['settings'] == json.loads(json.dumps(settings)) and set(saved['files']) == set(names) and all(
                        hashlib.sha256((folder/name).read_bytes()).hexdigest() == saved['files'][name] for name in names)
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            if not ready:
                folder.mkdir(parents=True, exist_ok=True)
                command = [sys.executable, '-m', 'tools.melee_anim.preview', '--model', str(model),
                           '--action', settings['action'], '--section', settings['section'],
                           '--output', str(folder), '--size', str(size), '--fps', str(settings['fps']),
                           '--backend', settings['backend'], '--pitch', str(angles[0]), '--yaw', str(angles[1]),
                           '--roll', str(angles[2]), '--still-frame', str(sample_index)]
                if companion:command += ['--companion', str(companion)]
                if power != 'none':command += ['--kirby-power', power]
                if center:command += ['--center-jump', 'on']
                if settings['action'].startswith(('attack-', 'tech-', 'movement-', 'other-')):
                    command += ['--attack-catalog', str(self.root/'attack-catalog.json')]
                if settings['action'].startswith('tech-'):
                    command += ['--ground-effects', 'on' if effects else 'off']
                if clip['character'] == 'game-and-watch' and settings['action'] in ('attack-305', 'attack-314'):
                    command += ['--judge-electric', 'on' if electric else 'off']
                timeline = folder/'timeline.json'
                if cycle == 'sync':
                    timeline.write_text(json.dumps(settings['sync_plan']))
                    command += ['--timeline', str(timeline)]
                else:
                    timeline.write_text(json.dumps(settings))
                    command += ['--samples', str(timeline)]
                with (folder/'render.log').open('w') as log:
                    with render_progress(folder/'render.log', 1, progress, png=True):
                        result = subprocess.run(command, cwd=self.repo, stdout=log, stderr=subprocess.STDOUT,
                                                timeout=600, env={**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
                if result.returncode:
                    raise RuntimeError(f'HD frame render failed; see {folder / "render.log"}')
                rendered = json.loads((folder/'preview-manifest.json').read_text())
                if (rendered['sample_source_times'] != [settings['source_times'][sample_index]] or
                        rendered.get('complete_interval') is not False or rendered.get('size') != size):
                    raise RuntimeError('HD render changed the selected frame or resolution')
                with Image.open(folder/'frame_0000.png') as image:
                    if image.size != (size, size) or image.mode != 'RGBA':
                        raise RuntimeError('HD render did not produce the expected RGBA PNG')
                    image.verify()
                saved = {'settings': settings, 'files': {name: hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in names}}
                temporary = marker.with_suffix('.json.tmp')
                temporary.write_text(json.dumps(saved, indent=2)+'\n')
                temporary.replace(marker)
            os.utime(folder, None)
            return folder/'frame_0000.png', key
