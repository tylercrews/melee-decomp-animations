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


def resize_gif(data, size):
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
    options = dict(save_all=True, append_images=frames[1:], duration=durations,
                   disposal=2, optimize=False)
    if looping is not None:
        options['loop'] = looping
    frames[0].save(out, format='GIF', **options)
    return out.getvalue()


class DownloadCatalog:
    def __init__(self, root, clips=None):
        self.root = Path(root).resolve()
        self.clips = collect_clips(self.root) if clips is None else clips
        self.cache = self.root/'downloads'/'resized'
        self.cache.mkdir(parents=True, exist_ok=True)

    def export(self, *, character, action, costume=0, size=256, kind='gif', scope='costume', frame=0):
        if size not in SIZES or kind not in ('gif', 'png') or scope not in ('costume', 'colors', 'all'):
            raise ValueError('Unsupported download option')
        if scope == 'all' and kind != 'gif':
            raise ValueError('All-character export is only available for GIFs')
        clips = [c for c in self.clips if scope == 'all' or
                 c['character'] == character and c['action_key'] == action and
                 (scope == 'colors' or c['costume_id'] == costume)]
        if not clips:
            raise ValueError('Unknown character, animation, or costume')
        if kind == 'png' and any(not 0 <= frame < len(c['frames']) for c in clips):
            raise ValueError('Frame index is outside this animation')
        entries = []
        for clip in clips:
            if kind == 'gif':
                source = self.root/clip['gif']
                name = sized_name(clip['download_name'], size)
            else:
                source = self.root/clip['frames'][frame]
                name = sized_name(clip['download_name'].replace('.gif', f'-frame-{frame+1:04d}.png'), size)
            data = source.read_bytes()
            key = hashlib.sha256(b'resize-v1\0'+str(size).encode()+b'\0'+kind.encode()+b'\0'+data).hexdigest()
            target = self.cache/f'{key}.{kind}'
            if not target.is_file():
                with Image.open(BytesIO(data)) as original:
                    same_size = original.size == (size, size)
                resized = data if same_size else (resize_gif if kind == 'gif' else resize_png)(data, size)
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
        if kind == 'png':
            name += f'-frame-{frame+1:04d}'
        if scope == 'colors':
            name += '-all-colors'
        return bundle, f'{name}-{size}px.zip', 'application/zip'
