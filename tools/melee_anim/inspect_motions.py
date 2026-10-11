"""Inspect extracted fighter motion references and nested results clips.

Run from the repository root:
  python -m tools.melee_anim.inspect_motions --output build/melee_anim/motions.json
The JSON contains metadata derived from local assets, not original asset bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

from .hsd import Archive, Dol, load_symbols, read_global
from .motions import MotionError, endpoint_report, read_figatree


RESULT_VARIANTS = {0: 0, 1: 2, 2: 5, 4: 9}


def motion_entries(archive: Archive, root: str, field: int, count: int) -> list[dict]:
    table = archive.pointer(archive.public(root) + field)
    if table is None:
        raise MotionError(f"{root} motion table is absent")
    archive.read(table, count * 24)
    result = []
    for index in range(count):
        at = table + index * 24
        size = archive.u32(at + 8)
        name_at = archive.pointer(at) if size else None
        if size and name_at is None:
            raise MotionError(f"motion {index} has no symbol name")
        flags = archive.u32(at + 16)
        script = archive.pointer(at + 12)
        result.append({"animation_id": index,
                       "symbol": archive.cstring(name_at) if name_at is not None else None,
                       "offset": archive.u32(at + 4), "size": size,
                       "motion_flags": f"0x{flags:08X}",
                       "motion_loop": bool(flags & (1 << 30)),
                       "script_offset": script})
    return result


def script_summary(archive: Archive, at: int | None, sizes: bytes) -> dict:
    """Read a linear script prefix; subroutine/goto pointers are reported.

    This does not run control flow, spawn items/effects, or apply visibility.
    These records identify why skeletal-only playback can miss behavior.
    """
    if at is None:
        return {"present": False}
    commands = []
    for _ in range(4096):
        word = archive.u32(at)
        opcode = word >> 26
        if opcode >= 10 + len(sizes):
            raise MotionError(f"unsupported fighter script opcode {opcode}")
        count = (2 if opcode in (5, 7) else 1) if opcode < 10 else sizes[opcode - 10]
        archive.read(at, count * 4)
        command = {"offset": at, "opcode": opcode, "first_word": f"0x{word:08X}"}
        if opcode in (5, 7):
            command["target"] = archive.pointer(at + 4)
        if opcode in (1, 2):
            command["timer_ticks"] = word & 0x3FFFFFF
        if opcode == 31:
            index, value = (word >> 19) & 127, word & 0x7FFFF
            command["visibility_group"] = index - 128 if index >= 64 else index
            command["visibility_value"] = value - 0x80000 if value >= 0x40000 else value
        if opcode == 40:
            idx, idx2, frame = (word >> 18) & 127, (word >> 11) & 127, word & 2047
            command["texture_animation"] = {
                "both": bool(word & (1 << 25)),
                "index": idx - 128 if idx >= 64 else idx,
                "index2": idx2 - 128 if idx2 >= 64 else idx2,
                "frame": frame - 2048 if frame >= 1024 else frame,
            }
        commands.append(command)
        if opcode in (0, 6, 7) or count == 0:
            return {"present": True, "scope": "linear prefix; control flow not executed",
                    "commands": commands, "opcodes": sorted({c["opcode"] for c in commands})}
        at += count * 4
    raise MotionError("script prefix exceeded bounded command count")


def read_exact_motion(blob: bytes | memoryview, motion: dict, label: str) -> Archive:
    at, size = motion["offset"], motion["size"]
    if not size or at < 0 or at + size > len(blob):
        raise MotionError(f"{label}: invalid packed motion range {at:#x}+{size:#x}")
    result = Archive(blob[at:at + size], f"{label}@{at:#x}")
    result.public(motion["symbol"])
    return result


def inspect(files: Path, dol_path: Path, symbols_path: Path,
            config_path: Path = Path("config/GALE01/config.yml")) -> dict:
    dol_bytes = dol_path.read_bytes()
    actual_hash = hashlib.sha1(dol_bytes).hexdigest()
    expected = re.search(r"^hash:\s*([0-9a-fA-F]{40})\s*$",
                         config_path.read_text(encoding="utf-8"), re.MULTILINE)
    if expected is None or actual_hash != expected[1].lower():
        raise MotionError("DOL SHA1 does not match the revision configured for these symbol tables")
    dol = Dol(dol_bytes, str(dol_path))
    symbols = load_symbols(symbols_path)
    names = read_global(dol, symbols, "ftData_803C1F40")
    packed_names = read_global(dol, symbols, "ftData_803C23E4")
    counts = read_global(dol, symbols, "ftData_Table_Unk0")
    demo_counts = read_global(dol, symbols, "ftData_UnkIntPairs")
    script_sizes = read_global(dol, symbols, "ftAction_803C0870")
    if (len(names) % 8 or len(counts) != len(names)
            or len(demo_counts) != len(names) or len(packed_names) != len(names) // 2):
        raise MotionError("inconsistent DOL fighter table sizes")
    fighter_roots = {}
    normal_tables = []
    mario = []
    selection = re.compile(r"_(?:Appeal|AttackS4|Damage|Down|Passive)")
    for kind in range(len(names) // 8):
        dat_pointer, symbol_pointer = struct.unpack_from(">2I", names, kind * 8)
        if not dat_pointer:
            continue
        filename, root = dol.cstring(dat_pointer), dol.cstring(symbol_pointer)
        archive = Archive((files / filename).read_bytes(), filename)
        fighter_roots[root] = (kind, filename, archive)
        aj_pointer = struct.unpack_from(">I", packed_names, kind * 4)[0]
        if not aj_pointer:
            continue
        count = struct.unpack_from(">I", counts, kind * 8 + 4)[0]
        aj_name = dol.cstring(aj_pointer)
        aj_bytes = (files / aj_name).read_bytes()
        instances = Archive.parse_packed(aj_bytes, aj_name)
        by_offset = dict(instances)
        motions = motion_entries(archive, root, 0xC, count)
        references = set()
        nonempty = 0
        for motion in motions:
            if not motion["size"]:
                continue
            at = motion["offset"]
            if at not in by_offset:
                raise MotionError(f"{root} animation {motion['animation_id']} begins between archives")
            packed = by_offset[at]
            if motion["size"] != packed.file_size:
                raise MotionError(f"{root} animation {motion['animation_id']} size mismatch")
            packed.public(motion["symbol"])
            references.add(at)
            nonempty += 1
            if root == "ftDataMario" and selection.search(motion["symbol"]):
                metadata, tracks = read_figatree(packed, motion["symbol"])
                mario.append({**motion, **metadata,
                              "effective_loop": metadata["tree_loop"] or motion["motion_loop"],
                              "script": script_summary(archive, motion["script_offset"], script_sizes)})
        normal_tables.append({"fighter_kind": kind, "fighter_archive": filename,
                              "fighter_root": root, "animation_file": aj_name,
                              "motion_count": count, "nonempty_motions_checked": nonempty,
                              "archive_instances": len(instances),
                              "unreferenced_archive_instances": len(instances) - len(references)})

    results = []
    for path in sorted(files.glob("GmRstM*.dat")):
        archive = Archive(path.read_bytes(), path.name)
        for public, base in archive.public_entries:
            if not public.startswith("ftDemoResultMotionFile"):
                continue
            root = public.replace("ftDemoResultMotionFile", "ftData", 1)
            if root not in fighter_roots:
                raise MotionError(f"{path.name}: no fighter data matching {public}")
            kind, dat_name, fighter = fighter_roots[root]
            count = struct.unpack_from(">I", demo_counts, kind * 8 + 4)[0]
            if count < 10:
                raise MotionError(f"{root} does not contain ten results animations")
            motions = motion_entries(fighter, root, 0x14, 10)
            extent_at, extent_size = archive.public_extent(public)
            packed_bytes = archive.read(extent_at, extent_size)
            packed_archives = dict(Archive.parse_packed(packed_bytes, f"{path.name}:{public}"))
            references = set()
            entries = []
            for motion in motions:
                if not motion["size"]:
                    entries.append(motion)
                    continue
                # The public names a byte array of packed complete archives,
                # not a FigaTree descriptor. Motion offsets start at that base.
                if motion["offset"] not in packed_archives:
                    raise MotionError(f"{root} demo animation begins between nested archives")
                packed = read_exact_motion(packed_bytes, motion, path.name)
                references.add(motion["offset"])
                metadata, tracks = read_figatree(packed, motion["symbol"])
                entries.append({**motion, **metadata,
                                "effective_loop": metadata["tree_loop"] or motion["motion_loop"],
                                "script": script_summary(fighter, motion["script_offset"], script_sizes),
                                "endpoint_check": endpoint_report(tracks, metadata["frames"])})
            results.append({"fighter_kind": kind, "fighter_root": root,
                            "fighter_archive": dat_name, "results_archive": path.name,
                            "motion_file_symbol": public, "motion_file_data_offset": base,
                            "motion_file_size": extent_size,
                            "nested_archives": len(packed_archives),
                            "unreferenced_nested_archives": len(packed_archives) - len(references),
                            "motions": entries})
    if not results:
        raise MotionError("no results animation archives were found")
    return {"format_version": 1,
            "dol_sha1": actual_hash, "revision_config": str(config_path),
            "evidence": "extracted asset structures plus original DOL tables; no rendered runtime validation",
            "results_variant_to_animation_id": RESULT_VARIANTS,
            "results_fighter_tables": len(results),
            "results_archive_count": len({r['results_archive'] for r in results}),
            "results_nonempty_motions": sum(bool(m['size']) for r in results for m in r['motions']),
            "normal_fighter_tables": len(normal_tables),
            "normal_nonempty_motions_checked": sum(t['nonempty_motions_checked'] for t in normal_tables),
            "normal_tables": normal_tables, "results": results,
            "mario_gameplay_examples": mario}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=Path, default=Path("orig/GALE01/files"))
    parser.add_argument("--dol", type=Path, default=Path("orig/GALE01/sys/main.dol"))
    parser.add_argument("--symbols", type=Path, default=Path("config/GALE01/symbols.txt"))
    parser.add_argument("--config", type=Path, default=Path("config/GALE01/config.yml"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = inspect(args.files, args.dol, args.symbols, args.config)
    except (OSError, ValueError, IndexError) as exc:
        parser.exit(1, f"motion inspection failed: {exc}\n")
    output = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(f"Checked {report['normal_nonempty_motions_checked']} ordinary motions across "
              f"{report['normal_fighter_tables']} fighter tables; "
              f"{report['results_nonempty_motions']} results clips across "
              f"{report['results_fighter_tables']} fighter tables in "
              f"{report['results_archive_count']} results archives. Report: {args.output}")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
