"""Find short repeatable clapping intervals in the existing rendered masters.

These are explicitly edited loops, not claims of exact authored periodicity.
All costumes must pass whole-image recurrence and unwrapped seam checks.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def find_minimum_cycle(samples):
    """Return the shortest eligible interval shared by every costume.

    samples has shape (costumes, frames, ...). A lag must be a substantial
    local recurrence minimum, not merely similar adjacent/held frames. Test
    the real unwrapped next frame, closing step, and velocity before cutting.
    """
    x = np.asarray(samples, dtype=np.float32)
    x = x.reshape(x.shape[0], x.shape[1], -1)
    count = x.shape[1]
    if count < 12:
        return None
    motion = np.mean(abs(x-x.mean(axis=1, keepdims=True)), axis=(1, 2))
    if np.any(motion < 1e-6):
        return None
    errors = np.array([np.zeros(len(x))] + [np.mean(abs(x[:, :-k]-x[:, k:]), axis=(1, 2))
                       for k in range(1, count//2+2)])
    for length in range(6, count//2+1):
        if not np.all((errors[length] < errors[length-1]) & (errors[length] < errors[length+1])):
            continue
        recurrence = errors[length]/motion
        peaks = errors[max(1, length//3):length].max(axis=0)
        improvement = 1-errors[length]/np.maximum(peaks, 1e-9)
        if np.any(recurrence > .9) or np.any(improvement < .35):
            continue
        candidates = []
        for start in range(count-length):
            segment = x[:, start:start+length+1]
            steps = np.mean(abs(np.diff(segment, axis=1)), axis=2)
            normal = steps.mean(axis=1)
            if np.any(normal < 1e-9):
                continue
            end_error = np.mean(abs(x[:, start+length]-x[:, start]), axis=1)
            closing = np.mean(abs(x[:, start]-x[:, start+length-1]), axis=1)
            velocity = np.mean(abs((x[:, start+1]-x[:, start]) -
                                  (x[:, start+length]-x[:, start+length-1])), axis=1)
            if (np.any(end_error > normal*.8) or
                    np.any(closing > np.percentile(steps, 90, axis=1)*1.25) or
                    np.any(velocity > normal*2)):
                continue
            score = float(np.max((end_error+velocity*.25)/normal))
            candidates.append((score, start, end_error/normal, closing/normal, velocity/normal))
        if candidates:
            score, start, end, closing, velocity = min(candidates, key=lambda c: (c[0], c[1]))
            return {'start': start, 'length': length, 'full_length': count, 'edited': True,
                    'checks': {'worst_recurrence_ratio': float(recurrence.max()),
                               'minimum_recurrence_improvement': float(improvement.min()),
                               'worst_unwrapped_endpoint_to_step': float(end.max()),
                               'worst_closing_step_to_mean': float(closing.max()),
                               'worst_velocity_to_step': float(velocity.max()), 'score': score}}
    return None


def read_cycles(root):
    path = Path(root)/'minimum-cycles.json'
    return json.loads(path.read_text())['characters'] if path.is_file() else {}


def input_fingerprint(manifests):
    """Invalidate analysis after any master/manifest is regenerated."""
    digest = hashlib.sha256()
    for path in manifests:
        data = path.read_bytes()
        digest.update(data)
        count = len(json.loads(data)['sample_source_times'])
        for i in range(count):
            stat = (path.parent/f'frame_{i:04d}.png').stat()
            digest.update(f'{i}:{stat.st_size}:{stat.st_mtime_ns}\n'.encode())
    return digest.hexdigest()


def attach_cycles(root, clips):
    for slug, cycle in read_cycles(root).items():
        if not cycle:
            continue
        manifests = sorted((Path(root)/slug).glob('costume_*/results-clap_source/preview-manifest.json'))
        if not manifests or cycle.get('input_fingerprint') != input_fingerprint(manifests):
            continue
        for clip in clips:
            if clip['character'] == slug and clip['action_key'] == 'results-clap_source':
                if (cycle['full_length'] != len(clip['frames']) or cycle['fps'] != clip['fps'] or
                        not 0 <= cycle['start'] < cycle['start']+cycle['length'] < len(clip['frames'])):
                    raise ValueError('Invalid minimum-cycle bounds')
                clip['minimum_cycle'] = {k: v for k, v in cycle.items() if k != 'input_fingerprint'}


def inspect_cycles(root):
    root = Path(root)
    report = {'method': 'edited contiguous PNG interval; conservative image recurrence/seam checks across every costume',
              'analysis_size': 64, 'fps_policy': 'preserve original output FPS; no speed change or blended frames',
              'characters': {}}
    for character in sorted(root.iterdir()):
        manifests = sorted(character.glob('costume_*/results-clap_source/preview-manifest.json'))
        if not manifests:
            continue
        models = [json.loads(p.read_text()) for p in manifests]
        first = models[0]
        if any(not m['complete_interval'] or not m['authored_loop'] or
               m['sample_source_times'] != first['sample_source_times'] or m['fps'] != first['fps'] for m in models):
            raise ValueError(f'Mismatched clapping timelines: {character.name}')
        count = len(first['sample_source_times'])
        samples = []
        for path in manifests:
            frames = []
            for i in range(count):
                with Image.open(path.parent/f'frame_{i:04d}.png') as image:
                    frames.append(np.asarray(image.convert('RGB').resize((64, 64), Image.Resampling.BOX), dtype=np.float32)/255)
            samples.append(frames)
        cycle = find_minimum_cycle(samples)
        if cycle:
            start, length = cycle['start'], cycle['length']
            cycle.update(fps=first['fps'], duration_seconds=length/first['fps'],
                         source_interval=[first['sample_source_times'][start], first['sample_source_times'][start+length]],
                         costume_count=len(manifests), input_fingerprint=input_fingerprint(manifests))
        report['characters'][character.name] = cycle
        print(f'{character.name}: {count} -> {cycle["length"]} frames, start {cycle["start"]}' if cycle else
              f'{character.name}: keep full {count}-frame loop', flush=True)
    (root/'minimum-cycles.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('build/melee_anim/preview'))
    args = parser.parse_args()
    inspect_cycles(args.root)


if __name__ == '__main__':
    main()
