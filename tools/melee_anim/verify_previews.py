"""Verify full-roster GIFs, lossless frame references, and download bundles.

Run after roster_batch and preview_gallery. Original data and generated
coverage stay local under ignored directories; no original asset fixtures.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image
from .catalog import CHARACTERS
from .preview_gallery import ACTIONS, collect_clips
from .roster import roster


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify(root):
    clips = collect_clips(root, include_attacks=False)
    expected = {(CHARACTERS[f['character_kind']][0], f'{a}_{s}', c['costume_id'])
                for f in roster()['fighters'] if not f['paired_member']
                for c in f['costumes'] for a, s, _ in ACTIONS}
    actual = {(c['character'], c['action_key'], c['costume_id']) for c in clips}
    if actual != expected:
        raise ValueError(f'Missing {sorted(expected-actual)}; unexpected {sorted(actual-expected)}')
    grouped = defaultdict(list)
    hashes = {}
    for clip in clips:
        grouped[(clip['character'], clip['action_key'])].append(clip)
        source = root/clip['gif']
        hashes[clip['download_name']] = digest(source.read_bytes())
        with Image.open(source) as im:
            looping = im.info.get('loop') == 0
            duration = 0
            for i in range(im.n_frames):
                im.seek(i)
                duration += im.info['duration']
            if looping != clip['authored_loop'] or duration != len(clip['frames'])*1000/clip['fps']:
                raise ValueError(f'GIF loop/duration mismatch: {source}')
            png = root/clip['frames'][min(67, len(clip['frames'])-1)]
            with Image.open(png) as still:
                if still.size != im.size:
                    raise ValueError(f'PNG/GIF size mismatch: {png}')
                still.verify()
    downloads = root/'downloads'
    def check_gif_bundle(path, group):
        with ZipFile(path) as archive:
            expected_names = {c['download_name'] for c in group}
            if set(archive.namelist()) != expected_names | {'manifest.json'}:
                raise ValueError(f'ZIP inventory mismatch: {path}')
            rows = json.loads(archive.read('manifest.json'))['files']
            if len(rows) != len(group) or {r['file'] for r in rows} != expected_names:
                raise ValueError(f'ZIP manifest mismatch: {path}')
            for row in rows:
                if row['sha256'] != hashes[row['file']] or digest(archive.read(row['file'])) != row['sha256']:
                    raise ValueError(f'ZIP hash mismatch: {path}/{row["file"]}')
    check_gif_bundle(downloads/'melee-all-characters-all-animations.zip', clips)
    still_bundle_count = 0
    for (slug, action), group in grouped.items():
        if len({hashes[c['download_name']] for c in group}) != len(group):
            raise ValueError(f'Costumes have duplicate GIF bytes: {slug}/{action}')
        check_gif_bundle(downloads/f'{slug}-{action.replace("_", "-")}-all-colors.zip', group)
        if len({len(c['frames']) for c in group}) != 1 or any(c['source_times'] != group[0]['source_times'] for c in group):
            raise ValueError(f'Costume timelines differ: {slug}/{action}')
        count = len(group[0]['frames'])
        folder = downloads/'stills'/f'{slug}-{action}'
        expected_stills = {f'frame-{i+1:04d}.zip' for i in range(count)}
        if {p.name for p in folder.glob('frame-*.zip')} != expected_stills:
            raise ValueError(f'Still ZIP frame inventory mismatch: {folder}')
        still_bundle_count += count
        # Verify first, final, and the user's example paused frame 68. Each
        # bundle must contain exactly the same displayed frame in each color.
        for i in {0, min(67, count-1), count-1}:
            with ZipFile(folder/f'frame-{i+1:04d}.zip') as archive:
                names = {c['download_name'].replace('.gif', f'-frame-{i+1:04d}.png') for c in group}
                if set(archive.namelist()) != names:
                    raise ValueError(f'Still ZIP costume inventory mismatch: {folder}/{i+1}')
                for clip in group:
                    name = clip['download_name'].replace('.gif', f'-frame-{i+1:04d}.png')
                    if archive.read(name) != (root/clip['frames'][i]).read_bytes():
                        raise ValueError(f'Still ZIP differs from player PNG: {folder}/{name}')
    result = {'characters': len({c['character'] for c in clips}), 'costumes': len({(c['character'], c['costume_id']) for c in clips}),
              'completed_jobs': len(clips), 'expected_jobs': len(expected), 'missing_jobs': [],
              'png_masters': sum(len(c['frames']) for c in clips), 'gif_bundles': len(grouped)+1,
              'still_frame_bundles': still_bundle_count,
              'checks': ['all GIF durations and loop flags', 'actual costume coverage',
                         'distinct GIF hashes within each action', 'all GIF ZIP inventories and hashes',
                         'all still ZIP filenames', 'first/frame 68/final still ZIP bytes per action'],
              'limitations': ['prototype shading and runtime behavior', 'no emulator reference comparison',
                              'player controls tested in Node, not a live browser']}
    (root/'coverage.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('build/melee_anim/preview'))
    args = parser.parse_args()
    print(json.dumps(verify(args.root), indent=2))


if __name__ == '__main__':
    main()
