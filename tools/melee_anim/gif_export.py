"""GIF frame-block encoding that preserves explicit repeated/held frames."""
from io import BytesIO
from PIL import Image, GifImagePlugin


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
    if loop is not None:
        options['loop'] = loop
    blocks, _ = GifImagePlugin.getheader(frames[0].copy(), info=options)
    out = BytesIO()
    for block in blocks:
        out.write(block)
    for frame, duration in zip(frames, durations):
        for block in GifImagePlugin.getdata(frame.copy(), duration=duration, disposal=2,
                                          include_color_table=False):
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
            frame = source.convert('RGB').quantize(palette=palette, dither=Image.Dither.NONE)
            frames.extend([frame]*(duration//tick_ms))
    return encode_frames(frames, [tick_ms]*len(frames), loop)
