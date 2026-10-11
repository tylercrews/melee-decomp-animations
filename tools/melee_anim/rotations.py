"""On-demand camera-angle masters; original models and timelines stay intact."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading


def camera_angles(pitch=0, yaw=0, roll=0):
    values = tuple(float(v) for v in (pitch, yaw, roll))
    if any(not math.isfinite(v) or abs(v) > 180 for v in values):
        raise ValueError('Camera angles must be between -180 and 180 degrees')
    # Canonicalize equivalent endpoints and negative zero, retaining precision.
    return tuple(0.0 if v == 0 else -180.0 if v == 180 else v for v in values)


def angle_tag(angles):
    return 'view-'+'-'.join(f'{axis}{value:g}' for axis, value in zip('xyz', angles))


def marked_angle(name, angles):
    path = Path(name)
    return f'{path.stem}-{angle_tag(angles)}{path.suffix}' if any(angles) else name


class RotationCache:
    """One render subprocess at a time, bounded duration, content-based resume.

    Always render 256px masters. Size downloads retain the existing resampling
    policy. Minimum/dirty intervals select these new full-clip masters; sync
    renders its exact fractional source-time plan separately.
    """
    def __init__(self, root, repo=None):
        self.root = Path(root).resolve()
        self.repo = Path(repo).resolve() if repo else Path(__file__).resolve().parents[2]
        self.lock = threading.RLock()

    def _inputs(self, clip, angles, sync, power='none', center=False):
        slug, cid = clip['character'], clip['costume_id']
        model = self.repo/'build/melee_anim/exported'/slug/f'costume_{cid:02d}'/'model.json'
        companion = model.parent/'companion/model.json'
        original = self.root/Path(clip['gif']).parent/'preview-manifest.json'
        manifest = json.loads(original.read_text())
        selected = manifest
        if sync:
            selected = json.loads((self.root/Path(clip['sync_cycle']['gif']).parent/'preview-manifest.json').read_text())
        action, section = clip['action_key'].rsplit('_', 1)
        paths = [original, model, self.repo/'build/melee_anim/motions.json']
        if power!='none':
            from .kirby_powers import model_for_power
            appearance,desc=model_for_power(self.repo,power,cid)
            paths += [appearance,desc['archive'],self.repo/'orig/GALE01/files/PlCo.dat']
            if desc['body']:paths.append(desc['body'])
            data=json.loads(appearance.read_text())
            paths.extend(appearance.parent/t['image_file'] for m in data['materials'] for t in m['textures'] if t.get('image_file'))
        if sync:
            paths.append(self.root/Path(clip['sync_cycle']['gif']).parent/'preview-manifest.json')
        report = json.loads(paths[2].read_text())
        for source in (model, companion) if companion.is_file() else (model,):
            data = json.loads(source.read_text())
            paths.append(source)
            paths.extend(source.parent/t['image_file'] for m in data['materials'] for t in m['textures'] if t.get('image_file'))
            if action.startswith(('attack-','tech-','movement-')):
                from .attacks import CATALOG, find_action
                attack_catalog = self.root/CATALOG
                actor = find_action(json.loads(attack_catalog.read_text()), data['fighter_kind'], action)
                archive = actor['animation_file']
                paths.append(attack_catalog)
                if action.startswith('tech-'):
                    paths.append(self.repo/'orig/GALE01/files/EfCoData.dat')
                    paths.append(self.repo/'orig/GALE01/files/PlCo.dat')
            elif action == 'taunt':
                table = next(t for t in report['taunts'] if t['fighter_kind'] == data['fighter_kind'])
                source_kind = table['standard_facing']['right']['source_fighter_kind']
                table = next(t for t in report['taunts'] if t['fighter_kind'] == source_kind)
                archive = table['animation_file']
            else:
                table = next(t for t in report['results'] if t['fighter_kind'] == data['fighter_kind'])
                archive = table['results_archive']
            paths.append(self.repo/'orig/GALE01/files'/archive)
        # Include evaluators, texture codecs and the renderer, not merely models.
        paths.extend(Path(__file__).parent.glob('*.py'))
        settings = {'version': 'camera-v1', 'angles': angles, 'action': action, 'section': section,
                    'kirby_power':power, 'center_jump':center,
                    'ground_effects':manifest.get('ground_effects_enabled',False),
                    'source_times': selected['sample_source_times'], 'fps': selected['fps'],
                    'sync_plan': selected.get('sync_plan') if sync else None,
                    'fit_source_times': manifest['sample_source_times'], 'size': 256,
                    'backend': 'native' if os.name == 'nt' else 'python',
                    'rotation_order': 'Ry(yaw) @ Rx(pitch) @ Rz(roll)',
                    'framing': 'per-costume whole-original-clip projected bounds'}
        digest = hashlib.sha256(json.dumps(settings, sort_keys=True).encode())
        for path in sorted(set(paths)):
            digest.update(str(path).encode())
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        return digest.hexdigest(), settings, model, companion if companion.is_file() else None

    def get(self, clip, angles, sync=False, power='none', center=False):
        angles = camera_angles(*angles)
        from .kirby_powers import validate_power
        validate_power(clip['character'],power)
        from .movement import centered_jump_setting
        centered_jump_setting(clip['action_key'],'on' if center else 'off')
        if not any(angles) and power=='none' and not center:
            return clip
        with self.lock:
            key, settings, model, companion = self._inputs(clip, angles, sync, power, center)
            folder = self.root/'rotations'/key
            done = folder/'rotation.json'
            ready = False
            if done.is_file():
                try:
                    completed = json.loads(done.read_text())
                    expected = {f'frame_{i:04d}.png' for i in range(len(settings['source_times']))} | {'preview.gif', 'preview-manifest.json'}
                    ready = (completed['settings'] == json.loads(json.dumps(settings)) and
                             set(completed['files']) == expected and
                             all((folder/name).is_file() and hashlib.sha256((folder/name).read_bytes()).hexdigest() == digest
                                 for name, digest in completed['files'].items()) and
                             len(completed['files']) == len(settings['source_times'])+2)
                except (ValueError, KeyError, OSError):
                    ready = False
            if not ready:
                folder.mkdir(parents=True, exist_ok=True)
                command = [sys.executable, '-m', 'tools.melee_anim.preview', '--model', str(model),
                           '--action', settings['action'], '--section', settings['section'],
                           '--output', str(folder), '--size', '256', '--fps', str(settings['fps']),
                           '--backend', settings['backend'], '--pitch', str(angles[0]),
                           '--yaw', str(angles[1]), '--roll', str(angles[2])]
                if power!='none':command += ['--kirby-power',power]
                if center:command += ['--center-jump','on']
                if companion:
                    command += ['--companion', str(companion)]
                if settings['action'].startswith(('attack-','tech-','movement-')):
                    from .attacks import CATALOG
                    command += ['--attack-catalog', str(self.root/CATALOG)]
                if settings['action'].startswith('tech-'):
                    command += ['--ground-effects','on' if settings['ground_effects'] else 'off']
                timeline = folder/'timeline.json'
                if sync:
                    timeline.write_text(json.dumps(settings['sync_plan']))
                    command += ['--timeline', str(timeline)]
                else:
                    timeline.write_text(json.dumps(settings))
                    command += ['--samples', str(timeline)]
                with (folder/'render.log').open('w') as log:
                    result = subprocess.run(command, cwd=self.repo, stdout=log, stderr=subprocess.STDOUT,
                                            timeout=600, env={**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
                if result.returncode:
                    raise RuntimeError(f'Camera render failed; see {folder / "render.log"}')
                manifest = json.loads((folder/'preview-manifest.json').read_text())
                if manifest['sample_source_times'] != settings['source_times']:
                    raise RuntimeError('Camera render changed the source timeline')
                names = [f'frame_{i:04d}.png' for i in range(len(settings['source_times']))]+['preview.gif', 'preview-manifest.json']
                completed = {'settings': settings, 'files': {n: hashlib.sha256((folder/n).read_bytes()).hexdigest() for n in names}}
                temporary = done.with_suffix('.json.tmp')
                temporary.write_text(json.dumps(completed, indent=2)+'\n')
                temporary.replace(done)
            relative = folder.relative_to(self.root).as_posix()
            if power!='none':
                clip={**clip,'kirby_power':power,'download_name':clip['download_name'].replace('.gif',f'-power-{power}.gif')}
            if center:clip={**clip,'download_name':clip['download_name'].replace('.gif','-centered.gif')}
            frames = [f'{relative}/frame_{i:04d}.png' for i in range(len(settings['source_times']))]
            if sync:
                return {**clip, 'sync_cycle': {**clip['sync_cycle'], 'frames': frames, 'gif': f'{relative}/preview.gif'}}
            return {**clip, 'frames': frames, 'gif': f'{relative}/preview.gif'}
