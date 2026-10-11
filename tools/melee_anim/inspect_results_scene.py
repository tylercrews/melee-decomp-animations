"""Inspect original results scene descriptors; no rendering or relocation.

Layouts come from src/melee/sc/types.h and baselib/{cobj,wobj}.h.
Run: python -m tools.melee_anim.inspect_results_scene
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

from .hsd import Archive, FormatError


def pointer_list(ar: Archive, offset: int | None) -> list[int]:
    result = []
    if offset is None:
        return result
    while offset + 4 <= ar.data_size:
        item = ar.pointer(offset)
        if item is None:
            return result
        result.append(item)
        offset += 4
    raise FormatError(f"{ar.label}: unterminated pointer array")


def vector(ar: Archive, at: int | None):
    return list(struct.unpack(">3f", ar.read(at, 12))) if at is not None else None


def inspect_scene(ar: Archive, name: str) -> dict:
    scene = ar.public(name)
    models = pointer_list(ar, ar.pointer(scene))
    camera = ar.pointer(scene + 4)
    lights = pointer_list(ar, ar.pointer(scene + 8))
    camera_data = None
    if camera is not None:
        desc = ar.pointer(camera)
        if desc is None:
            raise FormatError(f"{ar.label}: scene camera has no descriptor")
        projection = ar.u16(desc + 6)
        eye, target = ar.pointer(desc + 0x18), ar.pointer(desc + 0x1C)
        camera_data = {
            "offset": desc, "projection_type": projection,
            "viewport": list(struct.unpack(">4h", ar.read(desc + 8, 8))),
            "scissor": list(struct.unpack(">4H", ar.read(desc + 0x10, 8))),
            "eye": vector(ar, eye + 4 if eye is not None else None),
            "interest": vector(ar, target + 4 if target is not None else None),
            "near": ar.f32(desc + 0x28), "far": ar.f32(desc + 0x2C),
            "projection_parameters": list(struct.unpack(
                ">2f" if projection == 1 else ">4f",
                ar.read(desc + 0x30, 8 if projection == 1 else 16))),
            "animation_count": len(pointer_list(ar, ar.pointer(camera + 4))),
        }
    return {
        "public": name, "offset": scene,
        "model_count": len(models), "light_count": len(lights),
        "camera": camera_data,
        "models": [{"joint": ar.pointer(at),
                    "joint_animation_count": len(pointer_list(ar, ar.pointer(at + 4))),
                    "material_animation_count": len(pointer_list(ar, ar.pointer(at + 8))),
                    "shape_animation_count": len(pointer_list(ar, ar.pointer(at + 12)))}
                   for at in models],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=Path, default=Path("orig/GALE01/files"))
    parser.add_argument("--output", type=Path, default=Path("build/melee_anim/results_scene.json"))
    args = parser.parse_args()
    report = []
    for filename in ("GmRst.dat", "GmRst.usd"):
        path = args.files / filename
        if not path.exists():
            continue
        ar = Archive(path.read_bytes(), filename)
        report.append({"file": filename, "size": path.stat().st_size,
                       "publics": list(ar.publics),
                       "scenes": [inspect_scene(ar, name) for name in ("pnlsce", "flmsce")]})
    if not report:
        raise FormatError("No extracted GmRst.dat or GmRst.usd found")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for archive in report:
        for scene in archive["scenes"]:
            print(f"{archive['file']} {scene['public']}: {scene['model_count']} models, "
                  f"{scene['light_count']} lights; camera {scene['camera']}")
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
