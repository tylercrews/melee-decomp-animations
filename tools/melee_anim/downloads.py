"""Resize existing animation exports on demand, without changing source poses.

All cache files live under the ignored preview directory. Large images are
resampled from the current masters, not higher-detail model renders.
"""
import hashlib
import threading
import time
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED

from PIL import Image
from .preview_gallery import collect_clips
from .rotations import RotationCache, camera_angles, marked_angle
from .render_settings import native_size

SIZES = (128, 256, 512, 1024, 2048)


def sized_name(name, size):
    path = Path(name)
    return f'{path.stem}-{size}px{path.suffix}'


def resize_png(data, size):
    if size not in SIZES:
        raise ValueError('Unsupported download size')
    with Image.open(BytesIO(data)) as source:
        image = source.convert('RGBA').resize((size, size), Image.Resampling.LANCZOS)
        out = BytesIO()
        image.save(out, format='PNG')
        return out.getvalue()


def resize_gif(data, size, preserve_frames=False):
    """Preserve each decoded frame's delay and authored GIF loop metadata."""
    if size not in SIZES:
        raise ValueError('Unsupported download size')
    images, durations = [], []
    with Image.open(BytesIO(data)) as source:
        palette = source.copy()
        looping = source.info.get('loop')
        for i in range(source.n_frames):
            source.seek(i)
            durations.append(source.info.get('duration', 20))
            images.append(source.convert('RGBA').resize((size, size), Image.Resampling.LANCZOS))
    from .gif_export import encode_frames, quantize_rgba
    return encode_frames(quantize_rgba(images,palette),durations,looping)


def cycle_gif(root, clip, size, cycle=None):
    """Encode the chosen PNG interval at the original FPS, without endpoint duplication."""
    cycle = clip['minimum_cycle'] if cycle is None else cycle
    with Image.open(root/clip['gif']) as source:
        palette = source.copy()
    images = []
    for path in clip['frames'][cycle['start']:cycle['start']+cycle['length']]:
        with Image.open(root/path) as source:
            image = source.convert('RGBA')
            if image.size != (size, size):
                image = image.resize((size, size), Image.Resampling.LANCZOS)
            images.append(image)
    from .gif_export import encode_frames, quantize_rgba
    frames = quantize_rgba(images,palette)
    return encode_frames(frames,[1000//clip['fps']]*len(frames),0)


class DownloadCatalog:
    def __init__(self, root, clips=None):
        self.root = Path(root).resolve()
        catalog=self.root/'attack-catalog.json'
        import json
        self.clips = collect_clips(self.root) if clips is None else clips
        self.batch_catalog=json.loads(catalog.read_text()) if catalog.is_file() else {}
        self.cache = self.root/'downloads'/'resized'
        self.cache.mkdir(parents=True, exist_ok=True)
        self.rotations = RotationCache(self.root)
        from .attacks import AttackCache
        self.attacks = AttackCache(self.root)
        self.render_lock=threading.RLock()
        self.artifact_lock=threading.RLock()
        self.attacks.lock=self.render_lock
        self.rotations.lock=self.render_lock

    def preview(self, *, character, action, costume=0, cycle='full', pitch=0, yaw=0, roll=0, effects='off', power='none', center='off', electric='on'):
        from .movement import centered_jump_setting
        centered = centered_jump_setting(action,center)
        from .kirby_powers import validate_power
        validate_power(character,power)
        angles = camera_angles(pitch, yaw, roll)
        from .electric_burst import is_judge9
        if electric not in ('on','off') or electric=='off' and not is_judge9(character,action):raise ValueError('Electric explosion toggle requires Judgment9')
        if cycle not in ('full', 'minimum', 'dirty', 'sync'):
            raise ValueError('Unsupported clapping mode')
        if effects not in ('on','off') or effects=='on' and not action.startswith('tech-'):
            raise ValueError('Ground effects are only available for Tech animations')
        clip = next((c for c in self.clips if c['character'] == character and c['action_key'] == action and c['costume_id'] == costume), None)
        if clip is None:
            raise ValueError('Unknown character, animation, or costume')
        if cycle == 'sync' and (action != 'results-clap_source' or not clip.get('sync_cycle')):
            raise ValueError('Clapping-sync render is not available for this animation')
        clip = self.attacks.get(clip,effects=effects=='on',**({'electric':False} if electric=='off' else {}))
        clip = self.rotations.get(clip, angles, sync=cycle == 'sync', **({'power':power} if power!='none' else {}), **({'center':True} if centered else {}))
        if cycle == 'sync':
            frames = clip['sync_cycle']['frames']
        else:
            short = ((clip.get('dirty_cycle') if cycle == 'dirty' else None) or clip.get('minimum_cycle')) if cycle in ('minimum', 'dirty') and action == 'results-clap_source' else None
            frames = clip['frames'][short['start']:short['start']+short['length']] if short else clip['frames']
        times = clip.get('source_times', [])
        if cycle == 'sync':
            times = clip['sync_cycle']['source_times']
        elif short:
            times = times[short['start']:short['start']+short['length']]
        return {'frames': frames, 'angles': angles, 'source_times': times}

    def export(self, *, character, action, costume=0, size=None, kind='gif', scope='costume', frame=0, cycle='full', pitch=0, yaw=0, roll=0, effects='off', power='none', center='off', hats='off', electric='on'):
        if size is None:
            selected=next((c for c in self.clips if c['character']==character and c['action_key']==action),{})
            size=native_size(action,selected.get('animation_type'))
        from .electric_burst import is_judge9
        if electric not in ('on','off') or electric=='off' and not is_judge9(character,action):raise ValueError('Electric explosion toggle requires Judgment9')
        from .movement import centered_jump_setting
        centered = centered_jump_setting(action,center)
        from .kirby_powers import validate_power
        validate_power(character,power)
        if power!='none' and scope=='all' and hats!='all':raise ValueError('Select one Kirby animation for power exports')
        if hats not in ('off','all') or hats=='all' and scope=='costume':
            raise ValueError('Kirby Mode applies only to batch ZIP downloads')
        if hats=='all':power='none'
        angles = camera_angles(pitch, yaw, roll)
        if size not in SIZES or kind not in ('gif', 'png') or scope not in ('costume', 'colors', 'all') or cycle not in ('full', 'minimum', 'dirty', 'sync'):
            raise ValueError('Unsupported download option')
        if effects not in ('on','off') or effects=='on' and not action.startswith('tech-'):
            raise ValueError('Ground effects require a selected Tech animation')
        if scope == 'all' and kind != 'gif':
            raise ValueError('All-character export is only available for GIFs')
        if cycle == 'sync' and action != 'results-clap_source':
            raise ValueError('Clapping-sync alteration is only available for clapping')
        from .batch_exports import select_all,slug,enrich
        if scope=='all':clips,batch_label=select_all(enrich(self.clips,self.batch_catalog),character,action)
        else:
            clips=[c for c in self.clips if c['character']==character and c['action_key']==action and
                   (scope=='colors' or c['costume_id']==costume)]
            batch_label=''
        if cycle == 'sync':
            clips = [c for c in clips if c['action_key'] == 'results-clap_source']
            if any(not c.get('sync_cycle') for c in clips):
                raise ValueError('Sync render is not ready for every requested costume')
        if not clips:
            raise ValueError('Unknown character, animation, or costume')
        from .kirby_powers import powers
        jobs=[]
        for c in clips:
            variants=[p['slug'] for p in powers()] if hats=='all' and c['character']=='kirby' else [power if c['character']=='kirby' else 'none']
            jobs.extend((c,p) for p in variants)
        # Reject bad frame requests before starting an expensive render.
        for c in clips:
            short = ((c.get('dirty_cycle') if cycle == 'dirty' else None) or c.get('minimum_cycle')) if cycle in ('minimum', 'dirty') and c['action_key'] == 'results-clap_source' else None
            length = len(c['sync_cycle']['frames']) if cycle == 'sync' else short['length'] if short else c.get('frame_count',len(c['frames']))
            if kind == 'png' and not 0 <= frame < length:
                raise ValueError('Frame index is outside this animation')
        prepared=[];bases={}
        for c,variant in jobs:
            identity=(c['character'],c['action_key'],c['costume_id'])
            if identity not in bases:bases[identity]=self.attacks.get(c,effects=effects=='on',**({'electric':False} if electric=='off' and is_judge9(c['character'],c['action_key']) else {}))
            base=bases[identity]
            prepared.append(self.rotations.get(base,angles,sync=cycle=='sync',power=variant,center=centered))
            if len(jobs)>1:time.sleep(.005)
        clips=prepared
        if cycle == 'sync':
            clips = [{**c, 'gif': c['sync_cycle']['gif'], 'frames': c['sync_cycle']['frames'],
                      'fps': c['sync_cycle']['fps'],
                      'download_name': c['download_name'].replace('.gif', '-clapping-sync.gif')} for c in clips]
        if not clips:
            raise ValueError('Unknown character, animation, or costume')
        def selected_cycle(clip):
            if clip['action_key'] != 'results-clap_source' or cycle in ('full', 'sync'):
                return None
            return (clip.get('dirty_cycle') if cycle == 'dirty' else None) or clip.get('minimum_cycle')
        if kind == 'png' and any(not 0 <= frame < (selected_cycle(c)['length'] if selected_cycle(c) else len(c['frames'])) for c in clips):
            raise ValueError('Frame index is outside this animation')
        entries = []
        for clip in clips:
            short = selected_cycle(clip)
            suffix = '-dirty-loop' if short and short.get('dirty') else '-minimum-cycle'
            marked_name = clip['download_name'].replace('.gif', suffix+'.gif') if short else clip['download_name']
            marked_name = marked_angle(marked_name, angles)
            if kind == 'gif':
                source = self.root/clip['gif']
                name = sized_name(marked_name, size)
            else:
                source_index = short['start']+frame if short else frame
                source = self.root/clip['frames'][source_index]
                name = sized_name(marked_name.replace('.gif', f'-frame-{frame+1:04d}.png'), size)
            with self.artifact_lock:
                data = source.read_bytes()
                fingerprint = b''
                if short and kind == 'gif':
                    # Include every selected PNG and FPS, not just the old full GIF.
                    fingerprint = repr((short['start'], short['length'], clip['fps'])).encode()
                    for path in clip['frames'][short['start']:short['start']+short['length']]:
                        fingerprint += hashlib.sha256((self.root/path).read_bytes()).digest()
                key = hashlib.sha256(b'resize-v3-alpha\0'+str(size).encode()+b'\0'+kind.encode()+b'\0'+data+fingerprint).hexdigest()
                target = self.cache/f'{key}.{kind}'
                if not target.is_file():
                    with Image.open(BytesIO(data)) as original:
                        same_size = original.size == (size, size)
                    if short and kind == 'gif':
                        resized = cycle_gif(self.root, clip, size, short)
                    elif same_size:
                        resized = data
                    elif kind == 'gif':
                        resized = resize_gif(data, size, preserve_frames=cycle == 'sync')
                    else:
                        resized = resize_png(data, size)
                    temporary = target.with_suffix(target.suffix+'.tmp')
                    temporary.write_bytes(resized)
                    temporary.replace(target)
            entries.append((name, target, key))
        if scope == 'costume':
            name, target, _ = entries[0]
            return target, name, 'image/gif' if kind == 'gif' else 'image/png'
        bundle_key = hashlib.sha256(repr([(n, k) for n, _, k in entries]).encode()).hexdigest()
        if len({n for n,_,_ in entries})!=len(entries):raise ValueError('Batch has duplicate export filenames')
        bundle = self.cache/f'{bundle_key}.zip'
        with self.artifact_lock:
            if not bundle.is_file():
                temporary = bundle.with_suffix('.zip.tmp')
                with ZipFile(temporary, 'w', compression=ZIP_STORED) as archive:
                    for name, target, _ in entries:
                        archive.write(target, name)
                temporary.replace(bundle)
        name = 'melee-all-characters-'+slug(batch_label) if scope == 'all' else f'{character}-{action.replace("_", "-")}'
        if scope == 'all' and cycle == 'sync':
            name = 'melee-all-characters'
        if kind == 'png':
            name += f'-frame-{frame+1:04d}'
        if scope == 'colors':
            name += '-all-colors'
        if power!='none':name+=f'-power-{power}'
        if hats=='all' and any(c['character']=='kirby' for c in clips):name+='-kirby-all-hats-all-colors'
        if centered:name+='-centered'
        if any(selected_cycle(c) for c in clips):
            name += '-dirty-loop' if cycle == 'dirty' else '-minimum-cycle'
        if cycle == 'sync':
            name += '-clapping-sync'
        name = marked_angle(name+'.zip', angles)[:-4]
        return bundle, f'{name}-{size}px.zip', 'application/zip'
