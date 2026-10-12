"""GIF frame-block encoding that preserves explicit repeated/held frames."""
from io import BytesIO
from PIL import Image, GifImagePlugin
import numpy as np


def quantize_rgba(images, palette=None):
    """Reserve GIF index 0 for transparency; opaque black stays visible.

    PNG retains partial alpha. GIF uses alpha >=128, without a gray matte or
    RGB color-keying. Reuse one opaque 255-color palette across all frames.
    """
    if not images:
        raise ValueError('GIF requires images')
    images = [im.convert('RGBA') for im in images]
    if palette is not None and palette.info.get('transparency') == 0:
        colors = palette.getpalette()[3:768]
    else:
        count = min(8, len(images)); width, height = images[0].size
        tile = Image.new('RGB',(width*count,height))
        for i in range(count):
            rgba = np.array(images[i*len(images)//count])
            rgba[rgba[:,:,3] < 128,:3] = 0
            tile.paste(Image.fromarray(rgba[:,:,:3]),(i*width,0))
        colors = tile.quantize(colors=255).getpalette()[:765]
    colors = (colors+[0]*765)[:765]
    opaque = Image.new('P',(1,1)); opaque.putpalette(colors+colors[-3:])
    frames = []
    for image in images:
        indices = np.minimum(np.array(image.convert('RGB').quantize(palette=opaque,dither=Image.Dither.NONE)),254).astype(np.uint16)+1
        indices[np.array(image)[:,:,3] < 128] = 0
        frame = Image.fromarray(indices.astype(np.uint8)).convert('P')
        frame.putpalette([0,0,0]+colors)
        frame.info.update(transparency=0,background=0)
        frames.append(frame)
    return frames


def encode_frames(frames, durations, loop=None):
    """Write every palette frame, bypassing Pillow's adjacent-frame merging.

    Frames must share a palette. getheader/getdata are Pillow's exposed legacy
    GIF block APIs; use copied frames because header normalization can mutate.
    """
    if not frames or len(frames) != len(durations):
        raise ValueError('GIF requires one duration per frame')
    palette = frames[0].getpalette()
    if any(f.mode != 'P' or f.size != frames[0].size or f.getpalette() != palette for f in frames):
        raise ValueError('GIF frames must share size and palette')
    if any(d <= 0 or d % 10 for d in durations):
        raise ValueError('GIF durations must use positive 10ms ticks')
    options = {'optimize': False}
    transparency = frames[0].info.get('transparency')
    if any(f.info.get('transparency') != transparency for f in frames):
        raise ValueError('GIF frames must share transparency')
    if transparency is not None:
        options.update(transparency=transparency,background=transparency)
    if loop is not None:
        options['loop'] = loop
    blocks, _ = GifImagePlugin.getheader(frames[0].copy(), info=options)
    out = BytesIO()
    for block in blocks:
        out.write(block)
    for frame, duration in zip(frames, durations):
        settings = dict(duration=duration, disposal=2,include_color_table=False)
        if transparency is not None:
            settings['transparency'] = transparency
        for block in GifImagePlugin.getdata(frame.copy(), **settings):
            out.write(block)
    out.write(b';')
    return out.getvalue()


def expand_ticks(data, tick_ms=20):
    frames = []
    with Image.open(BytesIO(data)) as source:
        palette = source.copy()
        loop = source.info.get('loop')
        for i in range(source.n_frames):
            source.seek(i)
            duration = source.info['duration']
            if duration % tick_ms:
                raise ValueError('GIF delay is not an integer number of output ticks')
            frame = quantize_rgba([source.convert('RGBA')],palette)[0]
            frames.extend([frame]*(duration//tick_ms))
    return encode_frames(frames, [tick_ms]*len(frames), loop)
