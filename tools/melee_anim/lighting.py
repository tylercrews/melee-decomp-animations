"""Results-scene lights and the supported HSD diffuse/specular channels."""
from pathlib import Path
import hashlib

import numpy as np

from .hsd import Archive, FormatError
from .inspect_results_scene import pointer_list, vector


def results_lighting(files):
    path = Path(files)/'GmRst.usd'
    if not path.is_file():path = Path(files)/'GmRst.dat'
    data = path.read_bytes()
    ar = Archive(data, str(path))
    lights = []
    for entry in pointer_list(ar, ar.pointer(ar.public('pnlsce')+8)):
        desc = ar.pointer(entry)
        seen = set()
        while desc is not None:
            if desc in seen:raise FormatError('Cycle in results light descriptors')
            seen.add(desc)
            flags = ar.u16(desc+8)
            if (flags & 3) not in (0, 1):
                raise FormatError('Results lighting requires ambient/infinite source lights')
            pos = ar.pointer(desc+16)
            lights.append({'flags':flags, 'rgba':list(ar.read(desc+12, 4)),
                           'position':vector(ar, pos+4) if pos is not None else None})
            if pointer_list(ar, ar.pointer(entry+4)):
                raise FormatError('Animated results lights need an evaluator')
            desc = ar.pointer(desc+4)
    return {'source_archive':path.name, 'source_sha256':hashlib.sha256(data).hexdigest(),
            'scene':'pnlsce', 'lights':lights,
            'policy':'original results lights; orthographic viewer half-vector'}


def lighting_factors(material, normals, view, rig=None):
    """RGB factors before source texture composition; alpha is unaffected.

    HSD diffuse: clamp(material ambient * ambient light + N dot L).
    GX specular uses x*x / (shininess/2 + (1-shininess/2)*x*x),
    rather than an unrelated Phong exponent. The viewer supplies its own
    orthographic camera direction for the source half-vector calculation.
    """
    n = np.asarray(normals, dtype=float)
    n = n/np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)
    diffuse = np.ones_like(n)
    specular = np.zeros_like(n)
    if material.get('unlit'):
        return diffuse, specular
    if rig is None:
        light = np.array([-.35, .6, .72]);light /= np.linalg.norm(light)
        diffuse *= (.6+.4*np.maximum(0, n@light))[..., None]
        return diffuse, specular
    mode = material.get('render_mode', 0)
    if mode & 4:diffuse[:] = 0
    ambient = np.asarray((material.get('ambient_rgba') or [255]*4)[:3])/255
    for light in rig['lights']:
        flags = light['flags']
        if flags & 32:continue
        rgb = np.asarray(light['rgba'][:3])/255
        if (flags & 3) == 0:
            if mode & 4 and flags & 4:diffuse += ambient*rgb
            continue
        direction = np.asarray(light['position'], dtype=float)
        direction /= max(np.linalg.norm(direction), 1e-12)
        if mode & 4 and flags & 4:
            diffuse += np.maximum(0, n@direction)[..., None]*rgb
        if mode & 8 and flags & 8:
            half = direction+np.asarray(view)[:, 2]
            half /= max(np.linalg.norm(half), 1e-12)
            x2 = np.maximum(0, n@half)**2
            shininess = material.get('shininess')
            k = max(float(50 if shininess is None else shininess)/2, 1e-6)
            specular += (x2/np.maximum(k+(1-k)*x2, 1e-12))[..., None]*rgb
    return np.clip(diffuse, 0, 1), np.clip(specular, 0, 1)


def specular_texture(material):
    return next((t for t in material['textures'] if t.get('flags', 0) & 0x20
                 and t.get('coordinate_type', t.get('flags', 0) & 15) == 0
                 and t.get('image_file')), None)
