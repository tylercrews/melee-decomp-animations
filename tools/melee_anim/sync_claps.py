"""Plan and render a 42-frame / 0.84-second edited clapping timeline.

python -m tools.melee_anim.sync_claps --resume
Uses source-curve sampling, common costume intervals, short open-pose holds,
and wrist-gap phase markers. Mewtwo retains an idle rather than a fake clap.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
from .render_settings import RESULTS_SIZE
import subprocess
import sys

import numpy as np
from PIL import Image
from .cycles import input_fingerprint
from .hsd import Archive
from .preview import load_clip, pose_matrices

FRAME_COUNT = 42
FPS = 50
VERSION = 'clapping-sync-v1'


def fit_schedule(length, target=FRAME_COUNT, max_hold=3, tolerance=.20):
    options = []
    for repeats in range(1, target//length+5):
        for hold in range(max_hold+1):
            available = target-repeats*hold
            if available <= 0:
                continue
            rate = repeats*length/available
            if 1-tolerance-1e-9 <= rate <= 1+tolerance+1e-9:
                options.append((abs(rate-1)+.005*hold, repeats, hold, rate))
    if not options:
        raise ValueError(f'Cannot fit {length} moving frames into {target} frames')
    _, repeats, hold, rate = min(options)
    return {'repeats': repeats, 'hold_frames_per_cycle': hold, 'moving_rate': rate}


def timeline_indices(start, length, contact, buffer, schedule, target=FRAME_COUNT):
    """Continuous original-output indices; hold the open pose, align contact at t=0."""
    repeats, hold, rate = (schedule[k] for k in ('repeats', 'hold_frames_per_cycle', 'moving_rate'))
    period = target/repeats
    contact_phase = hold+((contact-buffer) % length)/rate
    result = []
    for tick in range(target):
        phase = (tick+contact_phase) % period
        distance = 0 if phase < hold else (phase-hold)*rate
        result.append(start+(buffer+distance) % length)
    return result


def best_cut(samples, length):
    """Least-disruptive common seam for the three explicitly requested extra cuts."""
    x = np.asarray(samples, dtype=np.float32)
    x = x.reshape(x.shape[0], x.shape[1], -1)
    choices = []
    for start in range(x.shape[1]-length):
        normal = np.mean(abs(np.diff(x[:, start:start+length+1], axis=1)), axis=(1, 2))
        normal = np.maximum(normal, 1e-8)
        end = np.mean(abs(x[:, start+length]-x[:, start]), axis=1)/normal
        velocity = np.mean(abs((x[:, start+1]-x[:, start])-
                              (x[:, start+length]-x[:, start+length-1])), axis=1)/normal
        choices.append((float(np.max(end+.25*velocity)), start))
    if not choices:
        raise ValueError('Cut needs an unwrapped terminal sample')
    return min(choices)[1]


def wrist_signal(model, manifest, motions, files):
    ar = Archive((files/'PlCo.dat').read_bytes())
    tables = ar.pointer(ar.public('ftLoadCommonData')+0x10)
    mapping = ar.pointer(ar.pointer(tables+model['fighter_kind']*4)+4)
    left, right = ar.u8(mapping+21), ar.u8(mapping+39)
    if max(left, right) >= len(model['bones']):
        return None
    _, metadata, tracks = load_clip(motions, 'results-clap', 'source', files, model['fighter_kind'])
    gaps = []
    for time in manifest['sample_source_times']:
        matrices = pose_matrices(model['bones'], tracks, time, metadata['type'])
        gaps.append(np.linalg.norm(matrices[left, :3, 3]-matrices[right, :3, 3]))
    if np.ptp(gaps) < 1e-5:
        return None
    return np.convolve(np.pad(gaps, (1, 1), mode='wrap'), np.ones(3)/3, mode='valid')


def plan_character(root, clips):
    first = clips[0]
    slug = first['character']
    manifests = [root/Path(c['gif']).parent/'preview-manifest.json' for c in clips]
    original = json.loads(manifests[0].read_text())
    model_path = Path('build/melee_anim/exported')/slug/'costume_00/model.json'
    model = json.loads(model_path.read_text())
    motions = json.loads(Path('build/melee_anim/motions.json').read_text())
    full_count = len(first['frames'])
    selected = first.get('dirty_cycle') or first.get('minimum_cycle')
    start, length = (selected['start'], selected['length']) if selected else (0, full_count)
    selection = 'dirty' if selected and selected.get('dirty') else 'minimum' if selected else 'full'
    extra = {'mewtwo': 25, 'pikachu': 15, 'pichu': 15}.get(slug)
    if extra:
        samples = []
        for clip in clips:
            frames = []
            for path in clip['frames']:
                with Image.open(root/path) as image:
                    frames.append(np.asarray(image.convert('RGB').resize((64, 64), Image.Resampling.BOX))/255)
            samples.append(frames)
        start, length = best_cut(samples, extra), extra
        selection = 'manual idle cut' if slug == 'mewtwo' else 'manual one-clap cut'
    signal = wrist_signal(model, original, motions, Path('orig/GALE01/files'))
    if signal is None:
        contact, buffer, marker = 0, 0, 'idle phase; no varying wrist gap'
    else:
        interval = signal[start:start+length]
        contact, buffer = int(np.argmin(interval)), int(np.argmax(interval))
        marker = 'default-costume minimum/maximum wrist-gap proxy'
    schedule = fit_schedule(length)
    indices = timeline_indices(start, length, contact, buffer, schedule)
    step = original['source_period_frames']/full_count
    times = [round(i*step, 10) for i in indices]
    return {'version': VERSION, 'character': slug, 'fps': FPS, 'length': FRAME_COUNT,
            'duration_seconds': FRAME_COUNT/FPS, 'selection': selection,
            'source_start_index': start, 'source_length': length, 'contact_index': contact,
            'buffer_index': buffer, 'phase_marker': marker, **schedule,
            'source_times': times, 'fit_source_times': original['sample_source_times'],
            'input_fingerprint': input_fingerprint(manifests), 'edited': True,
            'limitations': ['wrist gap is a phase proxy, not fingertip collision',
                            'different integer clap counts within the shared loop',
                            'selected dirty/manual seams remain possible']}


def attach_sync(root, clips):
    root = Path(root)
    path = root/'clapping-sync.json'
    if not path.is_file():
        return
    plans = json.loads(path.read_text())['characters']
    valid = {}
    for slug, plan in plans.items():
        manifests = sorted((root/slug).glob('costume_*/results-clap_source/preview-manifest.json'))
        valid[slug] = bool(manifests and input_fingerprint(manifests) == plan['input_fingerprint'])
    for clip in clips:
        if clip['action_key'] != 'results-clap_source' or not valid.get(clip['character']):
            continue
        plan = plans[clip['character']]
        folder = root/'clapping-sync'/clip['character']/f'costume_{clip["costume_id"]:02d}'
        manifest_path = folder/'preview-manifest.json'
        if not manifest_path.is_file():
            continue
        try:manifest = json.loads(manifest_path.read_text())
        except (ValueError,OSError):continue
        frames = [folder/f'frame_{i:04d}.png' for i in range(FRAME_COUNT)]
        if (manifest.get('sync_plan') != plan or not manifest.get('uniform_gif_ticks') or not (folder/'preview.gif').is_file() or
                not all(p.is_file() for p in frames)):
            continue
        clip['sync_cycle'] = {**{k: v for k, v in plan.items() if k not in ('input_fingerprint', 'fit_source_times')},
                              'frames': [p.relative_to(root).as_posix() for p in frames],
                              'gif': (folder/'preview.gif').relative_to(root).as_posix()}


def main():
    from .preview_gallery import collect_clips
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('build/melee_anim/preview'))
    parser.add_argument('--jobs', type=int, default=6)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--preserve-timing', action='store_true',help='retain existing 42-frame source schedules after a resolution-only rebuild')
    args = parser.parse_args()
    previous=json.loads((args.root/'clapping-sync.json').read_text())['characters'] if args.preserve_timing else {}
    if not 1 <= args.jobs <= 8:
        parser.error('jobs must be 1..8')
    clips = [c for c in collect_clips(args.root) if c['action_key'] == 'results-clap_source']
    plans, jobs = {}, []
    for slug in sorted({c['character'] for c in clips}):
        group = sorted([c for c in clips if c['character'] == slug], key=lambda c: c['costume_id'])
        if args.preserve_timing:
            old=previous[slug]
            manifests=[args.root/Path(c['gif']).parent/'preview-manifest.json' for c in group]
            if any(json.loads(p.read_text())['sample_source_times']!=old['fit_source_times'] for p in manifests):
                raise ValueError('Source timeline changed; regenerate the sync schedule')
            plan={**old,'input_fingerprint':input_fingerprint(manifests)}
        else:plan = plan_character(args.root, group)
        plans[slug] = plan
        print(f'{slug}: {plan["source_length"]} source samples; {plan["repeats"]} repeats; '
              f'{plan["hold_frames_per_cycle"]} held ticks; rate {plan["moving_rate"]:.3f}', flush=True)
        for clip in group:
            folder = args.root/'clapping-sync'/slug/f'costume_{clip["costume_id"]:02d}'
            folder.mkdir(parents=True, exist_ok=True)
            timeline = folder/'timeline.json'
            timeline.write_text(json.dumps(plan, indent=2)+'\n')
            model = Path('build/melee_anim/exported')/slug/f'costume_{clip["costume_id"]:02d}'/'model.json'
            old = folder/'preview-manifest.json'
            fingerprint = hashlib.sha256(model.read_bytes()).hexdigest()
            companion = model.parent/'companion/model.json'
            companion_hash = hashlib.sha256(companion.read_bytes()).hexdigest() if companion.is_file() else None
            if args.resume and old.is_file():
                try:data = json.loads(old.read_text())
                except (ValueError,OSError):data={}
                if (data.get('size')==RESULTS_SIZE and data.get('sync_plan') == plan and data.get('uniform_gif_ticks') and data.get('transparent_background') is True and data.get('model_sha256') == fingerprint and
                        data.get('companion_sha256') == companion_hash and (folder/'preview.gif').is_file() and
                        {p.name for p in folder.glob('frame_*.png')} == {f'frame_{i:04d}.png' for i in range(FRAME_COUNT)}):
                    continue
            jobs.append((folder, model, companion if companion.is_file() else None, timeline))
    (args.root/'clapping-sync.json').write_text(json.dumps({'duration_seconds': .84, 'frames': FRAME_COUNT, 'fps': FPS,
                                                        'characters': plans}, indent=2)+'\n')
    def render(job):
        folder, model, companion, timeline = job
        command = [sys.executable, '-m', 'tools.melee_anim.preview', '--model', str(model), '--action', 'results-clap',
                   '--output', str(folder), '--size', str(RESULTS_SIZE), '--backend', 'native', '--timeline', str(timeline)]
        if companion:
            command += ['--companion', str(companion)]
        with (folder/'render.log').open('w') as log:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                     env={**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
        return (str(folder), (folder/'render.log').read_text()[-1200:]) if process.returncode else None
    errors = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for i, future in enumerate(as_completed([pool.submit(render, job) for job in jobs]), 1):
            error = future.result()
            if error:
                errors.append(error)
                print('FAILED', error, flush=True)
            elif i % 10 == 0 or i == len(jobs):
                print(f'Rendered {i}/{len(jobs)} sync jobs', flush=True)
    (args.root/'clapping-sync-errors.json').write_text(json.dumps(errors, indent=2)+'\n')
    if errors:
        raise SystemExit(f'{len(errors)} sync jobs failed')
    print(f'Sync ready: {len(clips)} costumes, 42 frames / 0.84s each', flush=True)


if __name__ == '__main__':
    main()
