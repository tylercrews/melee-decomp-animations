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


def find_dirty_cycle(samples, approved=None):
    """Expose genuine recurrence candidates that failed the strict gates.

    Pick the shortest relaxed recurrence and its least disruptive common
    seam; retain every failed strict check for review instead of certifying it.
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
    ratios = errors/motion
    for length in range(6, count//2+1):
        if approved and length >= approved['length']:
            break
        if not ratios[length].mean() < min(ratios[length-1].mean(), ratios[length+1].mean()):
            continue
        peaks = errors[max(1, length//3):length].max(axis=0)
        improvement = 1-errors[length]/np.maximum(peaks, 1e-9)
        if ratios[length].mean() > 1.3 or ratios[length].max() > 1.6 or improvement.mean() < .10:
            continue
        phases = []
        for start in range(count-length):
            steps = np.mean(abs(np.diff(x[:, start:start+length+1], axis=1)), axis=2)
            normal = steps.mean(axis=1)
            if np.any(normal < 1e-9):
                continue
            end = np.mean(abs(x[:, start+length]-x[:, start]), axis=1)/normal
            closing = np.mean(abs(x[:, start]-x[:, start+length-1]), axis=1)/normal
            closing_limit = np.percentile(steps, 90, axis=1)*1.25/normal
            velocity = np.mean(abs((x[:, start+1]-x[:, start]) -
                                  (x[:, start+length]-x[:, start+length-1])), axis=1)/normal
            score = float(np.max(end+velocity*.25))
            phases.append((score, start, end, closing, closing_limit, velocity))
        if not phases:
            continue
        score, start, end, closing, closing_limit, velocity = min(phases, key=lambda row: (row[0], row[1]))
        failures = []
        if not np.all((errors[length] < errors[length-1]) & (errors[length] < errors[length+1])):
            failures.append('repeat timing varies by costume')
        if np.any(ratios[length] > .9):
            failures.append('body/pose varies between claps')
        if np.any(improvement < .35):
            failures.append('weak repetition / pose variation')
        if np.any(end > .8):
            failures.append('pose jump at wrap')
        if np.any(closing > closing_limit):
            failures.append('closing step is larger than usual')
        if np.any(velocity > 2):
            failures.append('speed/direction changes at wrap')
        if not failures:
            continue
        return {'start': start, 'length': length, 'full_length': count, 'edited': True, 'dirty': True,
                'failed_checks': failures,
                'checks': {'worst_recurrence_ratio': float(ratios[length].max()),
                           'minimum_recurrence_improvement': float(improvement.min()),
                           'worst_unwrapped_endpoint_to_step': float(end.max()),
                           'worst_closing_step_to_mean': float(closing.max()),
                           'worst_velocity_to_step': float(velocity.max()), 'score': score}}
    return None


def read_cycles(root, key='characters'):
    path = Path(root)/'minimum-cycles.json'
    return json.loads(path.read_text()).get(key, {}) if path.is_file() else {}


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
    for report_key, clip_key in [('characters', 'minimum_cycle'), ('dirty_characters', 'dirty_cycle')]:
        for slug, cycle in read_cycles(root, report_key).items():
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
                    clip[clip_key] = {k: v for k, v in cycle.items() if k != 'input_fingerprint'}


def inspect_cycles(root):
    root = Path(root)
    report = {'method': 'edited contiguous PNG interval; conservative image recurrence/seam checks across every costume',
              'analysis_size': 64, 'fps_policy': 'preserve original output FPS; no speed change or blended frames',
              'characters': {}, 'dirty_characters': {}}
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
        dirty = find_dirty_cycle(samples, cycle)
        for candidate in (cycle, dirty):
            if not candidate:
                continue
            start, length = candidate['start'], candidate['length']
            candidate.update(fps=first['fps'], duration_seconds=length/first['fps'],
                         source_interval=[first['sample_source_times'][start], first['sample_source_times'][start+length]],
                         costume_count=len(manifests), input_fingerprint=input_fingerprint(manifests))
        report['characters'][character.name] = cycle
        report['dirty_characters'][character.name] = dirty
        print(f'{character.name}: {count} -> {cycle["length"]} frames, start {cycle["start"]}' if cycle else
              f'{character.name}: keep full {count}-frame loop', flush=True)
        if dirty:
            print(f'  dirty review: {dirty["length"]} frames, start {dirty["start"]}: {", ".join(dirty["failed_checks"])}', flush=True)
    (root/'minimum-cycles.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def preserve_intervals(root):
    """Refresh fingerprints after resolution changes, retaining source cuts."""
    root=Path(root);path=root/'minimum-cycles.json';report=json.loads(path.read_text())
    for key in ('characters','dirty_characters'):
        for slug,cycle in report.get(key,{}).items():
            if not cycle:continue
            manifests=sorted((root/slug).glob('costume_*/results-clap_source/preview-manifest.json'))
            if len(manifests)!=cycle['costume_count']:raise ValueError('Costume coverage changed; reanalyze claps')
            for manifest in manifests:
                data=json.loads(manifest.read_text());times=data['sample_source_times']
                start,length=cycle['start'],cycle['length']
                if (len(times)!=cycle['full_length'] or data['fps']!=cycle['fps'] or
                    [times[start],times[start+length]]!=cycle['source_interval']):
                    raise ValueError('Source interval changed; reanalyze claps')
            cycle['input_fingerprint']=input_fingerprint(manifests)
    report['resolution_refresh']='Source intervals retained; no speed, phase or frame-count edits'
    temporary=path.with_suffix('.json.tmp');temporary.write_text(json.dumps(report,indent=2)+'\n');temporary.replace(path)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('build/melee_anim/preview'))
    parser.add_argument('--preserve-intervals',action='store_true',help='retain existing source cuts after a resolution-only rebuild')
    args = parser.parse_args()
    (preserve_intervals if args.preserve_intervals else inspect_cycles)(args.root)


if __name__ == '__main__':
    main()
