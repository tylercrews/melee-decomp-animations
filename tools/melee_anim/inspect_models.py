"""Inspect costume DAT assembly without relocating or rendering game code.

Run from the repo root: python -m tools.melee_anim.inspect_models
Reports skeleton topology, mesh/display-list layouts, envelope references and
texture/material metadata. Output is diagnostic, not a Blender importer.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from .hsd import Archive, Dol, FormatError, load_symbols, read_global


ATTR_NAMES = {0: "PNMTXIDX", 9: "POS", 10: "NRM", 11: "CLR0", 12: "CLR1",
              **{13 + i: f"TEX{i}" for i in range(8)}, 25: "NBT"}
PRIMITIVES = {0x80: "quads", 0x90: "triangles", 0x98: "triangle_strip",
              0xA0: "triangle_fan", 0xA8: "lines", 0xB0: "line_strip", 0xB8: "points"}
TEX_FORMATS = {0: "I4", 1: "I8", 2: "IA4", 3: "IA8", 4: "RGB565", 5: "RGB5A3",
               6: "RGBA8", 8: "C4", 9: "C8", 10: "C14X2", 14: "CMPR"}
MARIO_COSTUMES = [("PlMrNr.dat", "PlyMario5K_Share_joint"),
                  ("PlMrYe.dat", "PlyMario5KYe_Share_joint"),
                  ("PlMrBk.dat", "PlyMario5KBk_Share_joint"),
                  ("PlMrBu.dat", "PlyMario5KBu_Share_joint"),
                  ("PlMrGr.dat", "PlyMario5KGr_Share_joint")]


def floats(ar: Archive, at: int, count: int) -> list[float]:
    return list(struct.unpack(f">{count}f", ar.read(at, count * 4)))


def linked(ar: Archive, at: int | None, next_at: int):
    visited = set()
    while at is not None:
        if at in visited:
            raise FormatError(f"{ar.label}: linked-list cycle at {at:#x}")
        visited.add(at)
        yield at
        at = ar.pointer(at + next_at)


def joints(ar: Archive, root: int) -> list[dict]:
    result, visited = [], set()

    def walk(at, parent):
        while at is not None:
            if at in visited:
                raise FormatError(f"{ar.label}: joint cycle/shared non-instance at {at:#x}")
            visited.add(at)
            ar.read(at, 64)
            flags = ar.u32(at + 4)
            index = len(result)
            matrix = ar.pointer(at + 0x38)
            result.append({"index": index, "offset": at, "parent": parent,
                           "flags": flags, "rotation": floats(ar, at + 0x14, 3),
                           "scale": floats(ar, at + 0x20, 3),
                           "position": floats(ar, at + 0x2C, 3),
                           "inverse_bind_matrix": floats(ar, matrix, 12) if matrix is not None else None,
                           "dobj": ar.pointer(at + 0x10) if not flags & 0x4020 else None,
                           "robj": ar.pointer(at + 0x3C)})
            if not flags & 0x1000:  # INSTANCE children are references, not new nodes.
                walk(ar.pointer(at + 8), index)
            at = ar.pointer(at + 0xC)

    walk(root, None)
    return result


def attributes(ar: Archive, at: int) -> list[dict]:
    result = []
    for _ in range(64):
        attr = ar.u32(at)
        if attr == 255:
            return result
        ar.read(at, 24)
        result.append({"attribute": attr, "name": ATTR_NAMES.get(attr, str(attr)),
                       "type": ar.u32(at + 4), "components": ar.u32(at + 8),
                       "component_type": ar.u32(at + 12), "frac": ar.u8(at + 16),
                       "stride": ar.u16(at + 18), "array": ar.pointer(at + 20)})
        at += 24
    raise FormatError(f"{ar.label}: vertex descriptors lack terminator")


def attribute_size(desc: dict) -> int:
    attr, comp, typ = desc["attribute"], desc["components"], desc["component_type"]
    if attr <= 8:
        return 1  # GX matrix indices are direct bytes.
    if attr in (11, 12):
        try:
            return (2, 3, 4, 2, 3, 4)[typ]
        except IndexError as exc:
            raise FormatError("unsupported GX color type") from exc
    if attr == 9:
        count = 2 + comp
    elif attr in (10, 25):
        count = 3 if comp == 0 else 9
    elif 13 <= attr <= 20:
        count = 1 + comp
    else:
        raise FormatError(f"unsupported GX attribute {attr}")
    if typ not in range(5):
        raise FormatError(f"unsupported GX component type {typ}")
    return count * (1, 1, 2, 2, 4)[typ]


def display_lists(ar: Archive, at: int, length: int, descs: list[dict]) -> dict:
    """Bound GX primitive/index decoding; reject command types not yet supported."""
    data = ar.read(at, length)
    # GX serializes attributes in hardware VCD order; NBT occupies normal's slot.
    descs = sorted((d for d in descs if d["type"]),
                   key=lambda d: 10 if d["attribute"] == 25 else d["attribute"])
    counts, max_indices, matrix_indices = Counter(), {}, set()
    cursor, corners, triangles = 0, 0, 0
    first_positions = []

    def take(size):
        nonlocal cursor
        if cursor + size > length:
            raise FormatError(f"{ar.label}: truncated display list at {at + cursor:#x}")
        value = data[cursor:cursor + size]
        cursor += size
        return value

    while cursor < length:
        opcode = take(1)[0]
        if not opcode:
            if any(data[cursor:]):
                raise FormatError(f"{ar.label}: nonzero commands after display-list padding")
            break
        primitive = opcode & 0xF8
        if primitive not in PRIMITIVES or opcode & 7:
            raise FormatError(f"{ar.label}: unsupported GX command/VAT {opcode:#x}")
        count = int.from_bytes(take(2), "big")
        counts[PRIMITIVES[primitive]] += 1
        corners += count
        triangles += count // 3 if primitive == 0x90 else count // 4 * 2 if primitive == 0x80 else max(0, count - 2) if primitive in (0x98, 0xA0) else 0
        for _ in range(count):
            for d in descs:
                attr, typ = d["attribute"], d["type"]
                if attr <= 8:
                    if typ != 1:
                        raise FormatError("GX matrix index must be direct")
                    value = take(1)[0]
                    if attr == 0:
                        matrix_indices.add(value)
                    continue
                if typ == 1:
                    value_bytes = take(attribute_size(d))
                elif typ in (2, 3):
                    nindices = 3 if attr in (10, 25) and d["components"] == 2 else 1
                    index_bytes = take((typ - 1) * nindices)
                    idxs = [int.from_bytes(index_bytes[i:i + typ - 1], "big")
                            for i in range(0, len(index_bytes), typ - 1)]
                    maximum = max(idxs)
                    max_indices[attr] = max(max_indices.get(attr, 0), maximum)
                    if d["array"] is None or not d["stride"]:
                        raise FormatError("indexed GX attribute lacks array/stride")
                    # NBT3 carries three normal indices with three components each.
                    payload = attribute_size(d) // 3 if nindices == 3 else attribute_size(d)
                    ar.read(d["array"] + maximum * d["stride"], payload)
                    value_bytes = ar.read(d["array"] + idxs[0] * d["stride"], payload)
                else:
                    raise FormatError(f"unsupported GX attribute mode {typ}")
                if attr == 9 and len(first_positions) < 3:
                    code = ("B", "b", "H", "h", "f")[d["component_type"]]
                    n = 2 + d["components"]
                    xyz = struct.unpack(f">{n}{code}", value_bytes)
                    scale = 1 if code == "f" else 2 ** d["frac"]
                    first_positions.append([v / scale for v in xyz])
    return {"primitives": dict(counts), "corners": corners,
            "triangle_slots_including_degenerates": triangles,
            "max_indices": {ATTR_NAMES.get(k, str(k)): v for k, v in max_indices.items()},
            "matrix_indices": sorted(matrix_indices), "first_positions": first_positions}


def envelopes(ar: Archive, at: int | None, bone_offsets: dict) -> list[list[dict]]:
    result = []
    if at is None:
        return result
    for index in range(11):  # HSD renderer loads at most 10 matrices.
        env = ar.pointer(at + index * 4)
        if env is None:
            return result
        if index == 10:
            raise FormatError(f"{ar.label}: envelope palette exceeds 10 matrices")
        weights = []
        for entry in range(256):
            joint = ar.pointer(env + entry * 8)
            if joint is None:
                break
            if joint not in bone_offsets:
                raise FormatError(f"{ar.label}: envelope references absent joint {joint:#x}")
            weights.append({"joint_index": bone_offsets[joint],
                            "weight": ar.f32(env + entry * 8 + 4)})
        else:
            raise FormatError(f"{ar.label}: envelope weights lack terminator")
        result.append(weights)
    raise FormatError("envelope palette lacks terminator")


def material(ar: Archive, at: int) -> dict:
    ar.read(at, 24)
    mat, textures = ar.pointer(at + 12), []
    for tex in linked(ar, ar.pointer(at + 8), 4):
        ar.read(tex, 92)
        image, palette = ar.pointer(tex + 76), ar.pointer(tex + 80)
        detail = {"offset": tex, "flags": ar.u32(tex + 64),
                  "source": ar.u32(tex + 12), "blend": ar.f32(tex + 68),
                  "tev": ar.pointer(tex + 88)}
        if image is not None:
            ar.read(image, 24)
            fmt = ar.u32(image + 8)
            detail["image"] = {"offset": image, "texels": ar.pointer(image),
                               "width": ar.u16(image + 4), "height": ar.u16(image + 6),
                               "format": TEX_FORMATS.get(fmt, str(fmt)),
                               "mipmap": bool(ar.u32(image + 12)),
                               "min_lod": ar.f32(image + 16), "max_lod": ar.f32(image + 20)}
        if palette is not None:
            detail["palette"] = {"offset": palette, "data": ar.pointer(palette),
                                 "format": ar.u32(palette + 4), "entries": ar.u16(palette + 12)}
        textures.append(detail)
    return {"offset": at, "render_mode": ar.u32(at + 4),
            "diffuse_rgba": list(ar.read(mat + 4, 4)) if mat is not None else None,
            "alpha": ar.f32(mat + 12) if mat is not None else None,
            "textures": textures, "pixel_engine": ar.pointer(at + 20)}


def inspect_model(path: Path, symbol: str | None = None) -> dict:
    blob = path.read_bytes()
    ar = Archive(blob, str(path))
    if symbol is None:
        names = [name for name in ar.publics if name.endswith("_Share_joint")]
        if len(names) != 1:
            raise FormatError(f"{path}: choose root with --symbol; candidates={names}")
        symbol = names[0]
    bones = joints(ar, ar.public(symbol))
    bone_offsets = {b["offset"]: b["index"] for b in bones}
    drawables, polygons, materials = [], [], {}
    for b in bones:
        for dobj in linked(ar, b["dobj"], 4):
            ar.read(dobj, 16)
            mat = ar.pointer(dobj + 8)
            if mat is not None and mat not in materials:
                materials[mat] = material(ar, mat)
            drawable = {"index": len(drawables), "offset": dobj, "joint_index": b["index"],
                        "material": mat, "polygon_indices": []}
            for pobj in linked(ar, ar.pointer(dobj + 12), 4):
                ar.read(pobj, 24)
                desc = ar.pointer(pobj + 8)
                display = ar.pointer(pobj + 16)
                if desc is None or display is None:
                    raise FormatError(f"{path}: mesh lacks attributes/display list")
                attrs = attributes(ar, desc)
                flags = ar.u16(pobj + 12)
                mode = flags & 0x3000
                ref = ar.pointer(pobj + 20)
                entry = {"index": len(polygons), "offset": pobj,
                         "drawable_index": drawable["index"], "joint_index": b["index"],
                         "flags": flags, "mode": {0: "rigid_or_shared", 0x1000: "shape", 0x2000: "envelope"}.get(mode, "unknown"),
                         "attributes": attrs,
                         "display": display_lists(ar, display, ar.u16(pobj + 14) << 5, attrs)}
                if mode == 0x2000:
                    entry["envelopes"] = envelopes(ar, ref, bone_offsets)
                    for matrix_index in entry["display"]["matrix_indices"]:
                        if matrix_index % 3 or matrix_index // 3 >= len(entry["envelopes"]):
                            raise FormatError(f"{path}: GX matrix index absent from envelope palette")
                elif mode == 0:
                    if ref is not None and ref not in bone_offsets:
                        raise FormatError(f"{path}: shared vertex matrix references absent joint")
                    entry["shared_joint_index"] = bone_offsets.get(ref)
                elif mode == 0x1000:
                    entry["shape_set"] = ref
                else:
                    raise FormatError(f"{path}: unsupported polygon flags {flags:#x}")
                drawable["polygon_indices"].append(entry["index"])
                polygons.append(entry)
            drawables.append(drawable)
    summary = {"joints": len(bones), "drawables": len(drawables), "polygons": len(polygons),
               "materials": len(materials), "textures": sum(len(m["textures"]) for m in materials.values()),
               "mesh_modes": dict(Counter(p["mode"] for p in polygons)),
               "texture_formats": dict(Counter(t["image"]["format"] for m in materials.values()
                                               for t in m["textures"] if "image" in t)),
               "corners": sum(p["display"]["corners"] for p in polygons),
               "inverse_bind_matrices": sum(b["inverse_bind_matrix"] is not None for b in bones),
               "instance_joints": sum(bool(b["flags"] & 0x1000) for b in bones),
               "nonunit_scale_joints": sum(b["scale"] != [1.0, 1.0, 1.0] for b in bones),
               "relocation_count": len(ar.relocations), "extern_count": len(ar.extern_entries)}
    topology = [(b["parent"], b["rotation"], b["scale"], b["position"]) for b in bones]
    summary["bind_topology_sha256"] = hashlib.sha256(json.dumps(topology).encode()).hexdigest()
    return {"file": path.name, "root_symbol": symbol, "root_offset": ar.public(symbol),
            "archive_sha256": hashlib.sha256(blob).hexdigest(), "summary": summary,
            "joints": bones, "drawables": drawables, "polygons": polygons,
            "materials": list(materials.values())}


def resolved_filename(basename: str, language: str) -> str:
    """lbFileGetFullName's locale suffix rule for known game filenames."""
    if language not in ("us", "jp"):
        raise FormatError("language must be us or jp")
    stem, dot, suffix = basename.partition(".")
    return basename if dot and suffix else stem + (".usd" if language == "us" else ".dat")


def costume_catalog(files_root: Path, dol_path: Path, symbols_path: Path, language: str = "us") -> dict:
    """Validate selectable costume entries against the verified GALE01 DOL.

    The source's external CharacterKind and internal FighterKind differ. Read
    ftMapping_list rather than indexing costume tables with CharacterKind.
    Nana is an additional paired model; Zelda/Sheik are separate selectable
    forms and their extra transformed form must not duplicate costume jobs.
    """
    blob = dol_path.read_bytes()
    expected = "08e0bf20134dfcb260699671004527b2d6bb1a45"
    if hashlib.sha1(blob).hexdigest() != expected:
        raise FormatError("costume catalog requires matching GALE01 main.dol")
    dol, syms = Dol(blob, str(dol_path)), load_symbols(symbols_path)
    maps = read_global(dol, syms, "ftMapping_list")
    colors = read_global(dol, syms, "lbl_803D51A0")
    counts = read_global(dol, syms, "CostumeListsForeachCharacter")
    strings = read_global(dol, syms, "ftData_803C2360")
    reports, archives = [], {}

    def fighter(kind, ckind, paired):
        n = counts[kind * 8 + 4]  # UnkCostumeList.numCostumes is u8.
        table = struct.unpack_from(">I", strings, kind * 4)[0]
        if not 0 < n <= 16 or not table:
            raise FormatError(f"invalid costume count/table for fighter {kind}")
        output = []
        for costume_id in range(n):
            addresses = struct.unpack(">3I", dol.read(table + costume_id * 12, 12))
            basename, joint, mat = [dol.cstring(a) if a else None for a in addresses]
            if not basename or not joint:
                raise FormatError(f"missing costume file/joint for fighter {kind}")
            filename = resolved_filename(basename, language)
            if filename not in archives:
                archives[filename] = Archive((files_root / filename).read_bytes(), filename)
            ar = archives[filename]
            bone_list = joints(ar, ar.public(joint))
            mat_offset = ar.public(mat) if mat else None
            topology = [(b["parent"], b["rotation"], b["scale"], b["position"]) for b in bone_list]
            output.append({"costume_id": costume_id, "file": filename, "source_basename": basename,
                           "joint_symbol": joint, "joint_offset": ar.public(joint),
                           "material_animation_symbol": mat, "material_animation_offset": mat_offset,
                           "joints": len(bone_list),
                           "joint_hierarchy_sha256": hashlib.sha256(json.dumps([b["parent"] for b in bone_list]).encode()).hexdigest(),
                           "bind_topology_sha256": hashlib.sha256(json.dumps(topology).encode()).hexdigest()})
        reports.append({"character_kind": ckind, "fighter_kind": kind,
                        "paired_member": paired, "costume_count": n,
                        "costumes": output,
                        "identical_joint_hierarchy_all_costumes": len({c["joint_hierarchy_sha256"] for c in output}) == 1,
                        "identical_bind_topology_all_costumes": len({c["bind_topology_sha256"] for c in output}) == 1})
        return n

    for ckind in range(len(colors) // 4):
        kind, extra, transformation = maps[ckind * 3:ckind * 3 + 3]
        n = fighter(kind, ckind, False)
        if n != colors[ckind * 4]:
            raise FormatError(f"selectable/internal costume count mismatch for character {ckind}")
        if extra != 255 and not transformation:
            partner_n = fighter(extra, ckind, True)
            if partner_n != n:
                raise FormatError("paired fighter costume counts require explicit pairing")
    gw = Archive((files_root / "PlGw.dat").read_bytes(), "PlGw.dat")
    attr = gw.pointer(gw.public("ftDataGamewatch") + 4)
    if attr is None:
        raise FormatError("Game & Watch lacks external attributes")
    return {"language": language, "source_tables": {name: hex(syms[name][0]) for name in
                              ("ftMapping_list", "lbl_803D51A0", "CostumeListsForeachCharacter", "ftData_803C2360")},
            "selectable_forms": sum(not r["paired_member"] for r in reports),
            "selectable_costume_jobs": sum(r["costume_count"] for r in reports if not r["paired_member"]),
            "paired_member_costumes": sum(r["costume_count"] for r in reports if r["paired_member"]),
            "unique_model_archives": len(archives), "fighters": reports,
            "game_watch": {"attribute_offset": attr, "z_width": gw.f32(attr),
                           "costume_rgba": [list(gw.read(attr + 4 + i * 4, 4)) for i in range(4)],
                           "outline_rgba": list(gw.read(attr + 20, 4))}}


def visibility_lookup(ar, lookup, model_count):
    """Read one source FtPartsVisLookup array with bounded alternatives."""
    groups = []
    if lookup is None:
        return groups
    for group in range(model_count):
        count, alternatives = ar.u32(lookup + group * 8), ar.pointer(lookup + group * 8 + 4)
        if count > ar.data_size // 8:
            raise FormatError("visibility alternatives count exceeds archive")
        choices = []
        for option in range(count):
            if alternatives is None:
                raise FormatError("visibility alternatives missing")
            at = alternatives + option * 8
            size, indices = ar.u32(at), ar.pointer(at + 4)
            choices.append(list(ar.read(indices, size)) if indices is not None else [])
        groups.append(choices)
    return groups


def visibility_tables(path: Path, data_symbol: str, costume_count: int) -> dict:
    """Read FtPartsDesc alternatives; indices refer to preorder DObj lists.

    This reports the source lookup classes and alternatives. The selected
    alternatives still require loading/motion scripts and runtime callbacks.
    """
    ar = Archive(path.read_bytes(), str(path))
    parts = ar.pointer(ar.public(data_symbol) + 8)
    if parts is None:
        raise FormatError("fighter data lacks parts description")
    model_count, table = ar.u32(parts), ar.pointer(parts + 4)
    if not 0 <= model_count <= 11 or table is None:
        raise FormatError("invalid fighter visibility description")
    texture_count, texture_table = ar.u32(parts + 8), ar.pointer(parts + 12)
    if texture_count > 5 or texture_count and texture_table is None:
        raise FormatError("invalid fighter texture-animation description")
    output = []
    for costume in range(costume_count):
        classes = []
        for cls in range(4):
            lookup = ar.pointer(table + costume * 16 + cls * 4)
            fallback = lookup is None
            if fallback:
                lookup = ar.pointer(table + cls * 4)
            groups = visibility_lookup(ar, lookup, model_count)
            classes.append({"class": cls, "fallback_to_costume_0": fallback,
                            "lookup_offset": lookup, "groups": groups})
        tex_indices = []
        if texture_count:
            tex_map = ar.pointer(texture_table + costume * 4)
            if tex_map is None:
                tex_map = ar.pointer(texture_table)
            if tex_map is None:
                raise FormatError("fighter texture-animation map missing")
            tex_indices = list(struct.unpack(f">{texture_count}H", ar.read(tex_map, texture_count * 2)))
        output.append({"costume_id": costume, "classes": classes,
                       "script_texture_indices_to_global_tobj_indices": tex_indices})
    return {"file": path.name, "parts_offset": parts, "model_groups": model_count,
            "costumes": output}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--files-root", type=Path, default=Path("orig/GALE01/files"))
    parser.add_argument("--symbol", help="Model root symbol (only with one file)")
    parser.add_argument("--output", type=Path, default=Path("build/melee_anim/models.json"))
    parser.add_argument("--catalog", action="store_true", help="Validate all selectable costume model roots using matching GALE01 DOL")
    parser.add_argument("--all-models", action="store_true", help="Inspect all catalog model archives; store compact mesh/texture summaries")
    parser.add_argument("--dol", type=Path, default=Path("orig/GALE01/sys/main.dol"))
    parser.add_argument("--symbols", type=Path, default=Path("config/GALE01/symbols.txt"))
    parser.add_argument("--language", choices=("us", "jp"), default="us", help="Locale suffix selection for bare-dot filenames such as PlCaRe.")
    args = parser.parse_args()
    if args.symbol and len(args.files) != 1:
        parser.error("--symbol requires exactly one file")
    if args.all_models and args.files:
        parser.error("--all-models cannot be combined with individual files")
    catalog = costume_catalog(args.files_root, args.dol, args.symbols, args.language) if args.catalog or args.all_models else None
    if args.all_models:
        entries = dict.fromkeys((c["file"], c["joint_symbol"]) for f in catalog["fighters"] for c in f["costumes"])
        inputs = [(args.files_root / f, s) for f, s in entries]
    else:
        inputs = [(f, args.symbol) for f in args.files] if args.files else [(args.files_root / f, s) for f, s in MARIO_COSTUMES]
    reports = []
    for path, symbol in inputs:
        report = inspect_model(path, symbol)
        if args.all_models:
            report = {k: report[k] for k in ("file", "root_symbol", "root_offset", "archive_sha256", "summary")}
        reports.append(report)
    output = {"models": reports}
    if not args.files:
        output["mario_visibility"] = visibility_tables(args.files_root / "PlMr.dat", "ftDataMario", len(MARIO_COSTUMES))
    if catalog is not None:
        output["costume_catalog"] = catalog
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    console = {"output": str(args.output)}
    if catalog is not None:
        console["costumes"] = {k: catalog[k] for k in ("language", "selectable_forms", "selectable_costume_jobs", "paired_member_costumes", "unique_model_archives")}
    if args.all_models:
        console["models_inspected"] = len(reports)
        for key in ("texture_formats", "mesh_modes"):
            totals = Counter()
            for r in reports:
                totals.update(r["summary"][key])
            console[key] = dict(totals)
    else:
        console["models"] = [{"file": r["file"], **r["summary"]} for r in reports]
    print(json.dumps(console, indent=2))


if __name__ == "__main__":
    main()
