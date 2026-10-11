"""Resize existing animation exports on demand, without changing source poses.

All cache files live under the ignored preview directory. Large images are
resampled from the current masters, not higher-detail model renders.
"""
import hashlib
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED

from PIL import Image
from .preview_gallery import collect_clips
from .rotations import RotationCache, camera_angles, marked_angle

SIZES = (128, 256, 512, 1024)


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
    frames, durations = [], []
    with Image.open(BytesIO(data)) as source:
        palette = source.copy()
        looping = source.info.get('loop')
        for i in range(source.n_frames):
            source.seek(i)
            durations.append(source.info.get('duration', 20))
            frame = source.convert('RGB').resize((size, size), Image.Resampling.LANCZOS)
            frames.append(frame.quantize(palette=palette, dither=Image.Dither.NONE))
    out = BytesIO()
    if preserve_frames:
        from .gif_export import encode_frames
        return encode_frames(frames, durations, looping)
    options = dict(save_all=True, append_images=frames[1:], duration=durations,
                   disposal=2, optimize=False)
    if looping is not None:
        options['loop'] = looping
    frames[0].save(out, format='GIF', **options)
    return out.getvalue()


def cycle_gif(root, clip, size, cycle=None):
    """Encode the chosen PNG interval at the original FPS, without endpoint duplication."""
    cycle = clip['minimum_cycle'] if cycle is None else cycle
    with Image.open(root/clip['gif']) as source:
        palette = source.copy()
    frames = []
    for path in clip['frames'][cycle['start']:cycle['start']+cycle['length']]:
        with Image.open(root/path) as source:
            image = source.convert('RGB')
            if image.size != (size, size):
                image = image.resize((size, size), Image.Resampling.LANCZOS)
            frames.append(image.quantize(palette=palette, dither=Image.Dither.NONE))
    output = BytesIO()
    frames[0].save(output, format='GIF', save_all=True, append_images=frames[1:],
                   duration=1000//clip['fps'], loop=0, disposal=2, optimize=False)
    return output.getvalue()


class DownloadCatalog:
    def __init__(self, root, clips=None):
        self.root = Path(root).resolve()
        self.clips = collect_clips(self.root) if clips is None else clips
        self.cache = self.root/'downloads'/'resized'
        self.cache.mkdir(parents=True, exist_ok=True)
        self.rotations = RotationCache(self.root)

    def preview(self, *, character, action, costume=0, cycle='full', pitch=0, yaw=0, roll=0):
        angles = camera_angles(pitch, yaw, roll)
        if cycle not in ('full', 'minimum', 'dirty', 'sync'):
            raise ValueError('Unsupported clapping mode')
        clip = next((c for c in self.clips if c['character'] == character and c['action_key'] == action and c['costume_id'] == costume), None)
        if clip is None:
            raise ValueError('Unknown character, animation, or costume')
        if cycle == 'sync' and (action != 'results-clap_source' or not clip.get('sync_cycle')):
            raise ValueError('Clapping-sync render is not available for this animation')
        clip = self.rotations.get(clip, angles, sync=cycle == 'sync')
        if cycle == 'sync':
            frames = clip['sync_cycle']['frames']
        else:
            short = ((clip.get('dirty_cycle') if cycle == 'dirty' else None) or clip.get('minimum_cycle')) if cycle in ('minimum', 'dirty') and action == 'results-clap_source' else None
            frames = clip['frames'][short['start']:short['start']+short['length']] if short else clip['frames']
        return {'frames': frames, 'angles': angles}

    def export(self, *, character, action, costume=0, size=256, kind='gif', scope='costume', frame=0, cycle='full', pitch=0, yaw=0, roll=0):
        angles = camera_angles(pitch, yaw, roll)
        if size not in SIZES or kind not in ('gif', 'png') or scope not in ('costume', 'colors', 'all') or cycle not in ('full', 'minimum', 'dirty', 'sync'):
            raise ValueError('Unsupported download option')
        if scope == 'all' and kind != 'gif':
            raise ValueError('All-character export is only available for GIFs')
        if cycle == 'sync' and action != 'results-clap_source':
            raise ValueError('Clapping-sync alteration is only available for clapping')
        clips = [c for c in self.clips if scope == 'all' or
                 c['character'] == character and c['action_key'] == action and
                 (scope == 'colors' or c['costume_id'] == costume)]
        if cycle == 'sync':
            clips = [c for c in clips if c['action_key'] == 'results-clap_source']
            if any(not c.get('sync_cycle') for c in clips):
                raise ValueError('Sync render is not ready for every requested costume')
        if not clips:
            raise ValueError('Unknown character, animation, or costume')
        # Reject bad frame requests before starting an expensive render.
        for c in clips:
            short = ((c.get('dirty_cycle') if cycle == 'dirty' else None) or c.get('minimum_cycle')) if cycle in ('minimum', 'dirty') and c['action_key'] == 'results-clap_source' else None
            length = len(c['sync_cycle']['frames']) if cycle == 'sync' else short['length'] if short else len(c['frames'])
            if kind == 'png' and not 0 <= frame < length:
                raise ValueError('Frame index is outside this animation')
        if any(angles):
            clips = [self.rotations.get(c, angles, sync=cycle == 'sync') for c in clips]
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
            data = source.read_bytes()
            fingerprint = b''
            if short and kind == 'gif':
                # Include every selected PNG and FPS, not just the old full GIF.
                fingerprint = repr((short['start'], short['length'], clip['fps'])).encode()
                for path in clip['frames'][short['start']:short['start']+short['length']]:
                    fingerprint += hashlib.sha256((self.root/path).read_bytes()).digest()
            key = hashlib.sha256(b'resize-v2\0'+str(size).encode()+b'\0'+kind.encode()+b'\0'+data+fingerprint).hexdigest()
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
        bundle = self.cache/f'{bundle_key}.zip'
        if not bundle.is_file():
            temporary = bundle.with_suffix('.zip.tmp')
            with ZipFile(temporary, 'w', compression=ZIP_STORED) as archive:
                for name, target, _ in entries:
                    archive.write(target, name)
            temporary.replace(bundle)
        name = 'melee-all-characters-all-animations' if scope == 'all' else f'{character}-{action.replace("_", "-")}'
        if scope == 'all' and cycle == 'sync':
            name = 'melee-all-characters'
        if kind == 'png':
            name += f'-frame-{frame+1:04d}'
        if scope == 'colors':
            name += '-all-colors'
        if any(selected_cycle(c) for c in clips):
            name += '-dirty-loop' if cycle == 'dirty' else '-minimum-cycle'
        if cycle == 'sync':
            name += '-clapping-sync'
        name = marked_angle(name+'.zip', angles)[:-4]
        return bundle, f'{name}-{size}px.zip', 'application/zip'
