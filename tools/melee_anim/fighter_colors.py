"""Focused original PlCo color-script playback for Knockdown fighter flashes.

Only the color/wait/goto subset used by scripts 2 and 120 is supported. This
does not execute general fighter scripts or simulate hurtbox state transitions.
"""
import hashlib
import math
from pathlib import Path

import numpy as np
from PIL import Image

from .hsd import Archive, FormatError


def tech_color_animation(action):
    # Requested isolated preview: in-place entry flash and away-roll white
    # intangibility flash, with no fighter flash on the towards-roll preview.
    return {'tech-199': 120, 'tech-201': 2}.get(action.removesuffix('_source'))


def intangible_end_tick(motion):
    """Read the isolated tech's hit-status reset from its bounded source prefix."""
    script = motion.get('script', {})
    blocks = [script]+script.get('reachable_blocks', [])
    for block in blocks:
        tick = 0
        intangible = False
        for command in block.get('commands', []):
            opcode = command['opcode']
            if opcode == 1:
                tick += command['timer_ticks']
            elif opcode == 2:
                tick = command['timer_ticks']
            elif opcode == 26:
                status = int(command['first_word'], 16) & 0x3FFFFFF
                if status == 2:
                    intangible = True
                elif status == 0 and intangible:
                    return tick
    return motion['frames']


def color_samples(ar, start, count):
    """Evaluate integer game ticks using lb_80014258's post-command color step."""
    at, timer = start, 0
    color, delta = np.zeros(4), np.zeros(4)
    enabled = False
    samples = []
    for tick in range(count):
        if at is not None and timer:
            timer -= 1
        budget = 256
        while at is not None and timer <= 0:
            budget -= 1
            if not budget:
                raise FormatError('Color script has an unbounded zero-time loop')
            word = ar.u32(at); opcode, value = word >> 26, word & 0x3FFFFFF
            if opcode == 0:
                at = None
            elif opcode in (1, 2, 11):
                timer = value-tick if opcode == 2 else timer+value
                at += 4
            elif opcode == 7:
                at = ar.pointer(at+4)
                if at is None:
                    raise FormatError('Color script has a null goto')
            elif opcode in (10, 12, 20):
                if opcode in (10, 20):
                    enabled = False
                at = None if opcode == 10 else at+4
            elif opcode == 18:
                color = np.asarray(list(ar.read(at+4, 4)), dtype=float)
                delta = np.zeros(4); enabled = True; at += 8
            elif opcode == 19:
                if not value:
                    raise FormatError('Color blend has zero duration')
                target = np.asarray(list(ar.read(at+4, 4)), dtype=float)
                delta = (target+.5-np.trunc(color))/value
                at += 8
            else:
                raise FormatError(f'Unsupported focused color-script opcode {opcode}')
        if enabled:
            color += delta
        samples.append(np.clip(np.trunc(color), 0, 255).astype('uint8') if enabled else None)
    return samples


class TechFlash:
    def __init__(self, files, action, motion):
        self.animation_id = tech_color_animation(action)
        if self.animation_id is None:
            raise ValueError('This motion has no isolated fighter flash')
        blob = (Path(files)/'PlCo.dat').read_bytes()
        self.sha256 = hashlib.sha256(blob).hexdigest()
        ar = Archive(blob, 'PlCo.dat')
        table = ar.pointer(ar.public('ftLoadCommonData')+0x18)
        start = ar.pointer(table+8*self.animation_id)
        self.end_tick = intangible_end_tick(motion)
        self.samples = color_samples(ar, start, math.ceil(motion['frames'])+1)

    def apply(self, image, tick):
        if tick >= self.end_tick:
            return image
        color = self.samples[min(len(self.samples)-1, max(0, math.floor(tick)))]
        return blend_fighter_color(image, color)

    def provenance(self):
        return {'source_archive': 'PlCo.dat', 'source_sha256': self.sha256,
                'color_animation_id': self.animation_id, 'spawn_tick': 0,
                'hit_status_end_tick': self.end_tick,
                'policy': 'isolated in-place/away flash; no towards-roll fighter flash',
                'limitations': ['No full hurtbox/color-priority state machine']}


def blend_fighter_color(image, color):
    """ftMaterial color interpolation on covered fighter pixels; preserve alpha."""
    if color is None:
        return image
    rgba = np.asarray(image.convert('RGBA')).copy()
    alpha = float(color[3])/255
    rgba[:,:,:3] = np.clip(rgba[:,:,:3]*(1-alpha)+np.asarray(color[:3])*alpha, 0, 255).astype('uint8')
    return Image.fromarray(rgba)
