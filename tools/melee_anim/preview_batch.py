"""Render verified Mario pilot jobs for one or every actual costume.

Run: python -m tools.melee_anim.preview_batch --action all --section all --costume all --resume
The full roster is cataloged; rendering is deliberately limited to the
verified Mario rig until other fighter part/runtime behavior is implemented.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from .export_model import export_mario
from .render_settings import RESULTS_SIZE
from .inspect_models import costume_catalog



def action_sections(action, section):
    actions = ["results-clap", "victory1", "victory2", "victory3", "taunt"] if action == "all" else [action]
    if section == "wait" and any(not a.startswith("victory") for a in actions):
        raise ValueError("wait is only a section of a victory action")
    return [(a, s) for a in actions for s in
            (("source", "wait") if section == "all" and a.startswith("victory")
             else ("source",) if section == "all" else (section,))]


def completed_job(folder, model, action, section, size, files=Path('orig/GALE01/files')):
    """Resume only matching complete jobs with the exact expected file set."""
    path = folder / "preview-manifest.json"
    if not path.is_file():
        return False
    try:
        m = json.loads(path.read_text(encoding="utf-8"))
        if action=='results-clap' or action.startswith('victory'):
            from .lighting import results_lighting
            if m.get('lighting')!=results_lighting(files):return False
        if not (m["complete_interval"] and m["action"] == action and m["section"] == section
                and m["size"] == size and m["fps"] == 50 and m["camera_yaw"] == 0
                and m["nominal_ticks_per_second"] == 60
                and m.get('transparent_background') is True
                and m["model_sha256"] == hashlib.sha256(model.read_bytes()).hexdigest()):
            return False
        frames = {f"frame_{i:04d}.png" for i in range(len(m["sample_source_times"]))}
        actual = {p.name for p in folder.glob("frame_*.png")}
        return frames == actual and all((folder/name).stat().st_size > 0 for name in frames) and (folder/"preview.gif").stat().st_size > 0
    except (OSError, ValueError, KeyError, TypeError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("results-clap", "victory1", "victory2", "victory3", "taunt", "all"), default="all")
    parser.add_argument("--costume", default="all", help="actual Mario costume ID or all")
    parser.add_argument("--section", choices=("source", "wait", "all"), default="all")
    parser.add_argument("--size", type=int, default=RESULTS_SIZE, help="override native results master size")
    parser.add_argument("--jobs", type=int, default=3, help="concurrent render processes")
    parser.add_argument("--resume", action="store_true", help="verify and reuse completed compatible previews")
    parser.add_argument("--files", type=Path, default=Path("orig/GALE01/files"))
    parser.add_argument("--output", type=Path, default=Path("build/melee_anim/preview"))
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8 or (args.size is not None and not 64 <= args.size <= 1024):
        parser.error("jobs must be 1..8 and size 64..1024")
    try:
        choices = action_sections(args.action, args.section)
    except ValueError as exc:
        parser.error(str(exc))
    catalog = costume_catalog(args.files, Path("orig/GALE01/sys/main.dol"), Path("config/GALE01/symbols.txt"))
    costumes = next(f for f in catalog["fighters"] if f["fighter_kind"] == 0)["costumes"]
    valid = {c["costume_id"] for c in costumes}
    try:
        ids = sorted(valid) if args.costume == "all" else [int(args.costume)]
    except ValueError:
        parser.error("costume must be all or an actual integer ID")
    if any(i not in valid for i in ids):
        parser.error(f"supported Mario costume IDs: {sorted(valid)}")
    jobs, reused = [], 0
    for costume in ids:
        model_dir = Path("build/melee_anim/exported/mario") / f"costume_{costume:02d}"
        model, _ = export_mario(args.files, model_dir, costume)
        for action, section in choices:
            size = args.size
            folder = args.output / "mario" / f"costume_{costume:02d}" / f"{action}_{section}"
            if args.resume and completed_job(folder, model, action, section, size, args.files):
                reused += 1
                print(f"Verified existing costume {costume}: {action}/{section}", flush=True)
            else:
                jobs.append((costume, model, action, section, size, folder))

    def render(job):
        costume, model, action, section, size, folder = job
        env = {**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
        folder.mkdir(parents=True, exist_ok=True)
        with (folder/"render.log").open("w", encoding="utf-8") as log:
            result = subprocess.run([sys.executable, "-m", "tools.melee_anim.preview", "--model", str(model),
                                     "--files", str(args.files), "--action", action, "--section", section,
                                     "--size", str(size), "--output", str(folder)],
                                    env=env, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f"costume {costume} {action}/{section} failed; see {folder/'render.log'}")
        return f"costume {costume}: {action}/{section}"

    print(f"Rendering {len(jobs)} jobs; {reused} reused; concurrency {args.jobs}", flush=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(render, job) for job in jobs]
        for i, future in enumerate(as_completed(futures), 1):
            print(f"Completed {i}/{len(jobs)}: {future.result()}", flush=True)
    print(f"Ready: {len(jobs)+reused} action/costume previews", flush=True)


if __name__ == "__main__":
    main()
