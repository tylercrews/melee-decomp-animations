"""Render verified Mario pilot jobs for one or every actual costume.

Run: python -m tools.melee_anim.preview_batch --action results-clap --costume all
The full roster is cataloged; rendering is deliberately limited to the
verified Mario rig until other fighter part/runtime behavior is implemented.
"""

import argparse
from pathlib import Path
import subprocess
import sys

from .export_model import export_mario
from .inspect_models import costume_catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("results-clap", "victory1", "victory2", "victory3", "taunt", "all"), default="results-clap")
    parser.add_argument("--costume", default="all", help="actual Mario costume ID or all")
    parser.add_argument("--section", choices=("source", "wait"), default="source")
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--files", type=Path, default=Path("orig/GALE01/files"))
    parser.add_argument("--output", type=Path, default=Path("build/melee_anim/preview"))
    args = parser.parse_args()
    catalog = costume_catalog(args.files, Path("orig/GALE01/sys/main.dol"), Path("config/GALE01/symbols.txt"))
    costumes = next(f for f in catalog["fighters"] if f["fighter_kind"] == 0)["costumes"]
    valid = {c["costume_id"] for c in costumes}
    try:
        ids = sorted(valid) if args.costume == "all" else [int(args.costume)]
    except ValueError:
        parser.error("costume must be all or an actual integer ID")
    if any(i not in valid for i in ids):
        parser.error(f"supported Mario costume IDs: {sorted(valid)}")
    actions = ["results-clap", "victory1", "victory2", "victory3", "taunt"] if args.action == "all" else [args.action]
    if args.section == "wait" and any(not a.startswith("victory") for a in actions):
        parser.error("wait is only a section of a victory action")
    for costume in ids:
        model_dir = Path("build/melee_anim/exported/mario") / f"costume_{costume:02d}"
        model, _ = export_mario(args.files, model_dir, costume)
        for action in actions:
            folder = args.output / "mario" / f"costume_{costume:02d}" / f"{action}_{args.section}"
            print(f"Rendering Mario costume {costume}: {action}/{args.section}", flush=True)
            subprocess.run([sys.executable, "-m", "tools.melee_anim.preview", "--model", str(model),
                            "--files", str(args.files), "--action", action, "--section", args.section,
                            "--size", str(args.size), "--output", str(folder)], check=True)


if __name__ == "__main__":
    main()
