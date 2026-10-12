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
        if opcode==10:
            gfx,parameter=struct.unpack('>2H',archive.read(at+4,4))
            offsets=struct.unpack('>3h',archive.read(at+8,6))
            command['gfx_spawn']={'gfx_id':gfx,'raw_joint':(word>>18)&255,
                'common_joint':bool(word&(1<<17)),'destroy_on_state_change':bool(word&(1<<16)),
                'offset':[v/256 for v in offsets],
                'range':list(struct.unpack('>3H',archive.read(at+14,6))),'parameter':parameter}
        if opcode == 19:
            command["command_variable"] = {"index": (word >> 24) & 3,
                                           "value": word & 0xFFFFFF}
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


def state_entries(raw: bytes, first_state: int, table_name: str,
                  callback_names: dict[int, str]) -> list[dict]:
    """Read MotionState[ ] using its verified 32-byte source layout."""
    if len(raw) % 32:
        raise MotionError(f"{table_name}: incomplete MotionState array")
    states = []
    for index in range(len(raw) // 32):
        words = struct.unpack_from(">8I", raw, index * 32)
        states.append({"motion_state_id": first_state + index,
                       "animation_id": words[0] if words[0] < 0x80000000 else words[0] - 0x100000000,
                       "state_flags": f"0x{words[1]:08X}",
                       "table": table_name,
                       "animation_callback": callback_names.get(words[3]),
                       "animation_callback_address": f"0x{words[3]:08X}"})
    return states


def script_graph_summary(archive: Archive, start: int | None, sizes: bytes) -> dict:
    """Trace bounded static call/goto targets without executing game behavior."""
    root = script_summary(archive, start, sizes)
    if start is None:
        return root
    visited = {start}
    pending = [c["target"] for c in root["commands"] if "target" in c and c["target"] is not None]
    children = []
    while pending:
        at = pending.pop()
        if at in visited:
            continue
        if len(visited) >= 64:
            raise MotionError("script control-flow graph exceeded bounded targets")
        visited.add(at)
        child = script_summary(archive, at, sizes)
        children.append({"offset": at, **child})
        pending.extend(c["target"] for c in child["commands"]
                       if "target" in c and c["target"] is not None)
    root["reachable_blocks"] = children
    root["reachable_opcodes"] = sorted(set(root["opcodes"]).union(
        *(set(child["opcodes"]) for child in children)))
    root["scope"] = "static bounded control-flow graph; waits/loops and gameplay commands not executed"
    return root


def taunt_catalog(dol: Dol, symbols: dict, normal_sources: dict,
                  allowed_kinds: set[int], script_sizes: bytes) -> list[dict]:
    """Find taunt states by original DOL animation callback pointers.

    Common/character counts and animation IDs come from sized DOL tables.
    The only semantic selectors are the source's named Appeal callbacks,
    the special-taunt order table, and Nana's documented Popo fallback.
    """
    callbacks = {address: name for name, (address, _) in symbols.items()
                 if name.endswith("_AppealS_Anim")}
    common_raw = read_global(dol, symbols, "ftData_MotionStateList")
    common = state_entries(common_raw, 0, "ftData_MotionStateList", callbacks)
    standard = [s for s in common if s["animation_callback"] == "ftCo_AppealS_Anim"]
    if len(standard) != 2:
        raise MotionError("common taunt facing pair was not found in the DOL state table")
    table_pointers = read_global(dol, symbols, "ftData_CharacterStateTables")
    character_tables = {address: (name, size) for name, (address, size) in symbols.items()
                        if name.endswith("_Init_MotionStateTable")}
    special_order = struct.unpack(">6I", read_global(dol, symbols, "ASID_AppealS"))
    result = []
    by_root = {source["root"]: source for source in normal_sources.values()}
    for kind in sorted(allowed_kinds):
        source = normal_sources[kind]
        pointer = struct.unpack_from(">I", table_pointers, kind * 4)[0]
        custom = []
        if pointer:
            if pointer not in character_tables:
                raise MotionError(f"fighter {kind}: unknown sized character state table")
            name, size = character_tables[pointer]
            custom = [s for s in state_entries(dol.read(pointer, size), len(common), name, callbacks)
                      if s["animation_callback"] is not None]
        override = [s for s in custom if s["animation_callback"] != "ftFx_AppealS_Anim"]
        selected = override if override else standard
        if len(selected) != 2:
            raise MotionError(f"fighter {kind}: taunt override has no facing pair")

        def resolve(state: dict) -> tuple[dict, dict]:
            animation_id = state["animation_id"]
            if not 0 <= animation_id < len(source["motions"]):
                raise MotionError(f"fighter {kind}: taunt animation outside ordinary table")
            selected_source = source
            motion = source["motions"][animation_id]
            if not motion["size"] and source["root"] == "ftDataNana":
                selected_source = by_root["ftDataPopo"]
                motion = selected_source["motions"][animation_id]
            return selected_source, motion

        clips = {}

        def clip_for(state: dict) -> dict | None:
            clip_source, motion = resolve(state)
            if not motion["size"]:
                return None
            key = (clip_source["kind"], motion["animation_id"])
            if key not in clips:
                metadata, tracks = read_figatree(clip_source["archives"][motion["offset"]], motion["symbol"])
                clips[key] = {**motion, **metadata,
                              "source_fighter_kind": clip_source["kind"],
                              "source_fighter_archive": clip_source["filename"],
                              "animation_file": clip_source["animation_file"],
                              "effective_loop": metadata["tree_loop"] or motion["motion_loop"],
                              "state_references": [],
                              "script": script_graph_summary(clip_source["archive"],
                                                             motion["script_offset"], script_sizes),
                              "endpoint_check": endpoint_report(tracks, metadata["frames"])}
                opcodes = set(clips[key]["script"].get("reachable_opcodes", []))
                clips[key]["skeletal_only_omits"] = [label for relevant, label in (
                    ({10}, "spawned visual effects"), ({11, 16}, "hitboxes and attack interaction"),
                    ({17, 18, 38, 39}, "sound and voice commands"),
                    ({19}, "command variables used by fighter/item callbacks"),
                    ({31, 32, 33}, "model-part visibility changes"),
                    ({40}, "texture/material animation frame changes"),
                    ({41}, "additional part animation"),
                    ({46, 47}, "color-overlay animation"),
                ) if opcodes & relevant]
            if state not in clips[key]["state_references"]:
                clips[key]["state_references"].append(state)
            return clips[key]

        right = clip_for(selected[0])
        if right is None:
            raise MotionError(f"fighter {kind}: default taunt has no clip")
        left = clip_for(selected[1])
        left_state = selected[1] if left is not None else selected[0]
        left = left if left is not None else right
        facing = {}
        for direction, state, clip in (("right", selected[0], right), ("left", left_state, left)):
            facing[direction] = {"facing_direction": 1.0 if direction == "right" else -1.0,
                                 "motion_state_id": state["motion_state_id"],
                                 "animation_id": clip["animation_id"],
                                 "source_fighter_kind": clip["source_fighter_kind"],
                                 "left_archive_missing_fallback": direction == "left" and state is selected[0]}
        special = [s for s in custom if s["animation_callback"] == "ftFx_AppealS_Anim"]
        special_sequences = []
        if special:
            by_state = {s["motion_state_id"]: s for s in special}
            if set(by_state) != set(special_order):
                raise MotionError(f"fighter {kind}: special-taunt state order does not match ASID_AppealS")
            for index, direction in enumerate(("right", "left")):
                sequence = []
                for state_id in special_order[index * 3:index * 3 + 3]:
                    state = by_state[state_id]
                    clip = clip_for(state)
                    if clip is None:
                        raise MotionError(f"fighter {kind}: special taunt part has no clip")
                    sequence.append({"motion_state_id": state_id, "animation_id": clip["animation_id"],
                                     "source_fighter_kind": clip["source_fighter_kind"], "frames": clip["frames"]})
                special_sequences.append({"facing": direction, "parts": sequence,
                                          "transition": "ftFx_AppealS_Anim advances on !ftAnim_IsFramesRemaining",
                                          "scene_requirement": "Corneria or Venom stage eligibility, radio event and once-per-match logic"})
        runtime_notes = []
        if override:
            if any(s["animation_callback"] == "ftCl_AppealS_Anim" for s in override):
                runtime_notes.append({"requirement": "milk item spawned on left-thumb bone, animated and removed via command variables",
                                      "source": "src/melee/ft/kinds/ftCLink/ftclinkappeals.c:ftCl_AppealS_Anim"})
            if any(s["animation_callback"] == "ftDr_AppealS_Anim" for s in override):
                runtime_notes.append({"requirement": "random vitamin/pill item spawned, moved and removed via command variables; deterministic export must set its choice",
                                      "source": "src/melee/ft/kinds/ftDrMario/ftdrmarioappeals.c:ftDr_AppealS_Anim"})
        if source["root"] == "ftDataKirby":
            runtime_notes.append({"requirement": "standard taunt entry invokes copy-ability cleanup before selecting animation",
                                  "source": "src/melee/ft/kinds/ftCommon/ftCo_AppealS.c:ftCo_800DEBD0"})
        if source["root"] == "ftDataGanon":
            runtime_notes.append({"requirement": "standard taunt entry creates an additional effect via lb_800119DC",
                                  "source": "src/melee/ft/kinds/ftCommon/ftCo_AppealS.c:ftCo_800DEA28"})
        if source["root"] == "ftDataNana":
            runtime_notes.append({"requirement": "outside demo mode, missing Nana ordinary motion references resolve to Popo's same animation ID; pair with Popo/Nana costume mapping",
                                  "source": "src/melee/ft/ftdata.c:ftData_80085FD4"})
        result.append({"fighter_kind": kind, "fighter_root": source["root"],
                       "fighter_archive": source["filename"], "animation_file": source["animation_file"],
                       "role": "companion" if source["root"] == "ftDataNana" else "selectable_fighter_form",
                       "standard_entry_source": "src/melee/ft/kinds/ftCommon/ftCo_AppealS.c:ftCo_800DEA28 / ftCo_800DEAE8",
                       "standard_facing": facing,
                       "standard_states": selected,
                       "runtime_notes": runtime_notes,
                       "special_sequences": special_sequences,
                       "clips": list(clips.values())})
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
    normal_sources = {}
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
        normal_sources[kind] = {"kind": kind, "root": root, "filename": filename,
                                "archive": archive, "animation_file": aj_name,
                                "motions": motions, "archives": by_offset}
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
                                "script": script_graph_summary(fighter, motion["script_offset"], script_sizes),
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
    taunts = taunt_catalog(dol, symbols, normal_sources,
                           {r["fighter_kind"] for r in results}, script_sizes)
    return {"format_version": 2,
            "dol_sha1": actual_hash, "revision_config": str(config_path),
            "evidence": "extracted asset structures plus original DOL tables; no rendered runtime validation",
            "results_variant_to_animation_id": RESULT_VARIANTS,
            "results_fighter_tables": len(results),
            "results_archive_count": len({r['results_archive'] for r in results}),
            "results_nonempty_motions": sum(bool(m['size']) for r in results for m in r['motions']),
            "normal_fighter_tables": len(normal_tables),
            "normal_nonempty_motions_checked": sum(t['nonempty_motions_checked'] for t in normal_tables),
            "normal_tables": normal_tables, "results": results,
            "taunt_fighter_tables": len(taunts),
            "taunt_selectable_forms": sum(t["role"] == "selectable_fighter_form" for t in taunts),
            "taunt_clip_entries": sum(len(t["clips"]) for t in taunts), "taunts": taunts,
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
              f"{report['results_archive_count']} results archives; "
              f"{report['taunt_clip_entries']} taunt clip entries across "
              f"{report['taunt_selectable_forms']} selectable forms plus Nana. Report: {args.output}")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
