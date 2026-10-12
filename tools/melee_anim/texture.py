"""Decode base-level GameCube tiled textures and write RGBA PNGs.

No external dependency is needed. CMPR has four big-endian subblocks per 8x8
block, 3/8 interpolation, and colored transparent texels; ordinary PC BC1
decoding changes those pixels. Reference: Dolphin TextureDecoder_Generic.cpp
and TextureDecoder_Util.h in Source/Core/VideoCommon (checked 2026-10-10).
"""

import struct
import zlib
from pathlib import Path

from .hsd import FormatError


def rgb565(value):
    r, g, b = value >> 11, (value >> 5) & 63, value & 31
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2), 255)


def rgb5a3(value):
    if value & 0x8000:
        r, g, b = (value >> 10) & 31, (value >> 5) & 31, value & 31
        return ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2), 255)
    a, r, g, b = (value >> 12) & 7, (value >> 8) & 15, (value >> 4) & 15, value & 15
    return (r * 17, g * 17, b * 17, (a << 5) | (a << 2) | (a >> 1))


def image_size(width, height, fmt):
    layouts = {0: (8, 8, 32), 1: (8, 4, 32), 2: (8, 4, 32), 3: (4, 4, 32),
               4: (4, 4, 32), 5: (4, 4, 32), 6: (4, 4, 64), 8: (8, 8, 32),
               9: (8, 4, 32), 14: (8, 8, 32)}
    if width <= 0 or height <= 0 or fmt not in layouts:
        raise FormatError(f"unsupported GX image size/format {width}x{height}, {fmt}")
    tw, th, size = layouts[fmt]
    return ((width + tw - 1) // tw) * ((height + th - 1) // th) * size


def decode_image(data, width, height, fmt, palette=None, palette_format=1):
    required = image_size(width, height, fmt)
    if len(data) < required:
        raise FormatError("truncated tiled texture")
    out = bytearray(width * height * 4)

    def put(x, y, color):
        if x < width and y < height:
            at = (y * width + x) * 4
            out[at:at + 4] = bytes(color)

    def indexed(index):
        if palette is None or index * 2 + 2 > len(palette):
            raise FormatError("texture index outside palette")
        value = int.from_bytes(palette[index * 2:index * 2 + 2], "big")
        if palette_format == 0:
            return (value & 255,) * 3 + (value >> 8,)
        if palette_format == 1:
            return rgb565(value)
        if palette_format == 2:
            return rgb5a3(value)
        raise FormatError("unsupported GX palette format")

    if fmt == 14:
        at = 0
        for ty in range(0, height, 8):
            for tx in range(0, width, 8):
                for sy, sx in ((0, 0), (0, 4), (4, 0), (4, 4)):
                    c0, c1 = struct.unpack_from(">HH", data, at)
                    a, b = rgb565(c0), rgb565(c1)
                    if c0 > c1:
                        colors = (a, b, tuple((5 * a[i] + 3 * b[i]) >> 3 for i in range(3)) + (255,),
                                  tuple((3 * a[i] + 5 * b[i]) >> 3 for i in range(3)) + (255,))
                    else:
                        average = tuple((a[i] + b[i]) // 2 for i in range(3))
                        colors = (a, b, average + (255,), average + (0,))
                    for y in range(4):
                        selectors = data[at + 4 + y]
                        for x in range(4):
                            put(tx + sx + x, ty + sy + y, colors[(selectors >> (6 - 2 * x)) & 3])
                    at += 8
        return bytes(out)

    tw, th = (8, 8) if fmt in (0, 8) else (8, 4) if fmt in (1, 2, 9) else (4, 4)
    at = 0
    tile_size = 64 if fmt == 6 else 32
    for ty in range(0, height, th):
        for tx in range(0, width, tw):
            tile = data[at:at + tile_size]
            for y in range(th):
                for x in range(tw):
                    p = y * tw + x
                    if fmt in (0, 8):
                        value = (tile[p // 2] >> (4 if p % 2 == 0 else 0)) & 15
                        color = (value * 17,) * 4 if fmt == 0 else indexed(value)
                    elif fmt == 1:
                        color = (tile[p],) * 4
                    elif fmt == 2:
                        value = tile[p]
                        color = ((value & 15) * 17,) * 3 + ((value >> 4) * 17,)
                    elif fmt == 3:
                        a, i = tile[p * 2:p * 2 + 2]
                        color = (i, i, i, a)
                    elif fmt == 4:
                        color = rgb565(int.from_bytes(tile[p * 2:p * 2 + 2], "big"))
                    elif fmt == 5:
                        color = rgb5a3(int.from_bytes(tile[p * 2:p * 2 + 2], "big"))
                    elif fmt == 6:
                        color = (tile[p * 2 + 1], tile[32 + p * 2], tile[33 + p * 2], tile[p * 2])
                    elif fmt == 9:
                        color = indexed(tile[p])
                    put(tx + x, ty + y, color)
            at += tile_size
    return bytes(out)


def write_png(path: Path, width: int, height: int, rgba: bytes):
    if len(rgba) != width * height * 4:
        raise FormatError("RGBA image size mismatch")
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = b"".join(b"\0" + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))
    encoded = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
