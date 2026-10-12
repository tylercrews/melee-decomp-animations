"""Export a fighter costume as neutral JSON meshes plus decoded PNG textures.

Matrices are row-major 4x4 arrays multiplying column vectors. Coordinates stay
in the game's axes (Y up); the render backend owns any coordinate conversion.
Both convenient bind geometry and exact source palette bindings are retained.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

import numpy as np

from .hsd import Archive, FormatError
from .inspect_models import attribute_size, costume_catalog, inspect_model, linked, visibility_tables, visibility_lookup
from .motions import Track
from .roster import roster, visibility_defaults, visible_drawables
from .texture import decode_image, image_size, write_png


def matrix4(values):
    result = np.eye(4)
    result[:3, :] = np.asarray(values).reshape(3, 4)
    return result


def local_matrix(rotation, scale, position, parent_scale=None):
    """HSD_MtxSRT: Euler Rz*Ry*Rx, with HSD parent-scale compensation."""
    x, y, z = rotation
    sx, cx, sy, cy, sz, cz = math.sin(x), math.cos(x), math.sin(y), math.cos(y), math.sin(z), math.cos(z)
    rotation = np.array([[cz * cy, cz * sx * sy - cx * sz, cz * cx * sy + sx * sz],
                         [sz * cy, sz * sx * sy + cx * cz, sz * cx * sy - sx * cz],
                         [-sy, cy * sx, cy * cx]])
    result = np.eye(4)
    result[:3, :3] = rotation @ np.diag(scale)
    if parent_scale is not None:
        if np.any(np.asarray(parent_scale) == 0):
            raise FormatError("zero parent scale cannot be compensated")
        result[:3, :3] = np.diag(1 / np.asarray(parent_scale)) @ result[:3, :3] @ np.diag(parent_scale)
    result[:3, 3] = position
    return result


def world_matrices(bones, poses=None):
    """Compose HSD local transforms; poses overrides rotation/scale/position."""
    matrices, scales = [], []
    for bone in bones:
        if bone["flags"] & (0x20000 | 0x1000000 | 0x2000000):
            raise FormatError("quaternion/independent joint matrices need a separate evaluator")
        pose = poses[bone["index"]] if poses is not None else bone
        parent = bone["parent"]
        parent_scale = scales[parent] if parent is not None else None
        current_scale = parent_scale if bone["flags"] & 8 else np.asarray(pose["scale"]) * (parent_scale if parent_scale is not None else 1)
        local = local_matrix(pose["rotation"], pose["scale"], pose["position"], parent_scale)
        matrices.append(matrices[parent] @ local if parent is not None else local)
        scales.append(current_scale)
    return matrices


def palette_matrices(bones, worlds, envelopes):
    """Mario skeleton-root skin rule from ftPartsSetupEnvelopeMtx."""
    result = []
    for envelope in envelopes:
        if not envelope:
            raise FormatError("empty envelope")
        if envelope[0]["weight"] >= 1.0:
            result.append(np.asarray(worlds[envelope[0]["joint_index"]]))
        else:
            blended = np.zeros((4, 4))
            for influence in envelope:
                joint = influence["joint_index"]
                inverse = bones[joint]["inverse_bind_matrix"]
                if inverse is None:
                    raise FormatError("weighted joint lacks stored envelope matrix")
                blended += influence["weight"] * (worlds[joint] @ matrix4(inverse))
            blended[3] = [0, 0, 0, 1]
            result.append(blended)
    return result


def skin_source_mesh(mesh, bones, worlds):
    """Evaluate exact source positions and inverse-transpose blended normals."""
    palettes = palette_matrices(bones, worlds, mesh["envelopes"])
    source = np.asarray(mesh["source_positions"], dtype=float)
    normals = np.asarray(mesh["source_normals"], dtype=float)
    indices = np.asarray(mesh["palette_indices"])
    positions, transformed_normals = np.zeros_like(source), np.zeros_like(normals)
    for index, matrix in enumerate(palettes):
        selected = indices == index
        positions[selected] = source[selected] @ matrix[:3, :3].T + matrix[:3, 3]
        # Zero-scale channels collapse/hide parts; their normal matrix is
        # singular, but they must not abort the rest of a valid fighter pose.
        normal_matrix = np.linalg.pinv(matrix[:3, :3]).T
        transformed_normals[selected] = normals[selected] @ normal_matrix.T
    lengths = np.linalg.norm(transformed_normals, axis=1)
    good = lengths > 1e-12
    transformed_normals[good] /= lengths[good, None]
    return positions, transformed_normals


def decode_mesh(ar, polygon):
    """Decode primitive corners, preserving UV seams and skin palette indices."""
    attrs = sorted((a for a in polygon["attributes"] if a["type"]), key=lambda a: 10 if a["attribute"] == 25 else a["attribute"])
    at = polygon["offset"]
    display = ar.read(ar.pointer(at + 16), ar.u16(at + 14) << 5)
    cursor, vertices, triangles, keys = 0, [], [], []

    def take(size):
        nonlocal cursor
        if cursor + size > len(display):
            raise FormatError("truncated primitive")
        value = display[cursor:cursor + size]
        cursor += size
        return value

    while cursor < len(display):
        opcode = take(1)[0]
        if opcode == 0:
            break
        if opcode & 7:
            raise FormatError("only GX VAT0 is supported")
        count = int.from_bytes(take(2), "big")
        start = len(vertices)
        for _ in range(count):
            vertex = {"matrix": 0, "uvs": {}}
            position_key = None
            for desc in attrs:
                attr, typ = desc["attribute"], desc["type"]
                if attr <= 8:
                    value = take(1)[0]
                    if attr == 0:
                        if value % 3:
                            raise FormatError("invalid position matrix index")
                        vertex["matrix"] = value // 3
                    continue
                if attr in (11, 12):
                    if typ in (2,3):
                        index=int.from_bytes(take(typ-1),"big");value=ar.read(desc["array"]+index*desc["stride"],attribute_size(desc))
                    else:value=take(attribute_size(desc))
                    if attr == 11 and desc['component_type'] == 4:
                        vertex['color'] = [v/255 for v in value]+[1]*(4-len(value))
                    continue
                if attr not in (9, 10, 25, 13, 14, 15, 16, 17, 18, 19, 20):
                    raise FormatError(f"unsupported pilot vertex attribute {attr}")
                size = attribute_size(desc)
                if typ in (2, 3):
                    n=3 if attr in (10,25) and desc["components"]==2 else 1
                    indices=[int.from_bytes(take(typ-1),"big") for _ in range(n)]
                    if n==3:size//=3
                    value = ar.read(desc["array"] + indices[0] * desc["stride"], size)
                elif typ == 1:
                    value = take(size)
                else:
                    raise FormatError("unsupported vertex attribute mode")
                code = ("B", "b", "H", "h", "f")[desc["component_type"]]
                components = len(value)//(1,1,2,2,4)[desc["component_type"]]
                decoded = struct.unpack(f">{components}{code}", value)
                fraction = 1 if code == "f" else 2 ** desc["frac"]
                decoded = [v / fraction for v in decoded]
                if attr == 9:
                    vertex["position"] = (decoded+[0,0,0])[:3]
                    position_key = value
                elif attr in (10,25):
                    vertex["normal"] = decoded[:3]
                else:
                    vertex["uvs"][str(attr - 13)] = decoded
            if "position" not in vertex:raise FormatError("mesh lacks positions")
            vertex.setdefault("normal",[0,0,1])
            vertices.append(vertex)
            keys.append((position_key, vertex["matrix"]))
        primitive = opcode & 0xF8
        if primitive == 0x90:
            if count % 3:
                raise FormatError("triangle vertex count is not divisible by three")
            triangles.extend([start + i, start + i + 1, start + i + 2] for i in range(0, count, 3))
        elif primitive == 0x98:
            triangles.extend([start + i - 2, start + i - 1, start + i] if i % 2 == 0 else
                             [start + i - 2, start + i, start + i - 1] for i in range(2, count))
        elif primitive == 0xA0:
            triangles.extend([start, start + i - 1, start + i] for i in range(2, count))
        elif primitive == 0x80:
            if count % 4:
                raise FormatError("quad vertex count is not divisible by four")
            for i in range(0, count, 4):
                triangles.extend(([start + i, start + i + 1, start + i + 2],
                                  [start + i, start + i + 2, start + i + 3]))
        else:
            raise FormatError(f"unsupported mesh primitive {primitive:#x}")
    original_count = len(triangles)
    triangles = [t for t in triangles if len({keys[i] for i in t}) == 3]
    return {"source_positions": [v["position"] for v in vertices],
            "source_normals": [v["normal"] for v in vertices],
            "palette_indices": [v["matrix"] for v in vertices],
            "uvs": [v["uvs"].get("0", [0, 0]) for v in vertices],
            "colors": [v.get('color',[1,1,1,1]) for v in vertices],
            "uv_sets": {key: [v["uvs"].get(key, [0, 0]) for v in vertices]
                        for key in sorted({k for v in vertices for k in v["uvs"]})},
            "triangles": triangles, "degenerate_triangle_slots_dropped": original_count - len(triangles)}


def texture_animations(ar, root):
    """Match material-animation tree nodes to JObj/DObj descriptors."""
    result = {}
    if root is None:
        return result
    def walk(joint, node):
        while joint is not None and node is not None:
            dobj = ar.pointer(joint + 16)
            anim = ar.pointer(node + 8)
            while dobj is not None and anim is not None:
                material_at = ar.pointer(dobj + 8)
                for texanim in linked(ar, ar.pointer(anim + 8), 0):
                    result[(material_at, ar.u32(texanim + 4))] = texanim
                dobj, anim = ar.pointer(dobj + 4), ar.pointer(anim)
            walk(ar.pointer(joint + 8), ar.pointer(node))
            joint, node = ar.pointer(joint + 12), ar.pointer(node + 4)
    symbol = root.replace("_Share_joint", "_Share_matanim_joint")
    if symbol in ar.publics:
        walk(ar.public(root), ar.public(symbol))
    return result


def aobj_frame0(ar, at):
    values = {}
    if at is None:
        return values
    for fobj in linked(ar, ar.pointer(at + 8), 0):
        source = ar.pointer(fobj + 16)
        track = Track(-1, ar.u8(fobj + 12), int(ar.f32(fobj + 8)), ar.u8(fobj + 13),
                      ar.u8(fobj + 14), ar.read(source, ar.u32(fobj + 4)))
        value = track.evaluate(0)
        if value is not None:
            values[track.channel] = value
    return values


def texture_matrix(texture):
    """MakeTextureMtx from tobj.c: S * R * T, with repeat and mirror offset."""
    scale = texture["scale"]
    rs, rt = texture["repeat_s"], texture["repeat_t"]
    if not rs or not rt:
        raise FormatError("texture repeats cannot be zero")
    s = [rs / scale[0] if abs(scale[0]) >= 2 ** -23 else 0,
         rt / scale[1] if abs(scale[1]) >= 2 ** -23 else 0, scale[2]]
    rotation = texture["rotation"].copy()
    rotation[2] = -rotation[2]
    translation = texture["translation"]
    t = [-translation[0], -(translation[1] + (scale[1] / rt if texture["wrap_t"] == 2 else 0)), translation[2]]
    return np.diag(s + [1]) @ local_matrix(rotation, [1, 1, 1], [0, 0, 0]) @ local_matrix([0, 0, 0], [1, 1, 1], t)


def primary_drawables(count, classes, item_groups=()):
    """Classes 0/1/3/4 address the primary list; class 2 uses fp->x203C.

    Exclude alternate normal/metal/item geometry from the initial primary
    list while retaining every option the normal motion scripts may select.
    """
    normal = {d for group in classes[0]["groups"] for option in group for d in option}
    hidden = {d for cls in (classes[1], classes[3]) for group in cls["groups"] for option in group for d in option}
    hidden.update(d for group in item_groups for option in group for d in option)
    return set(range(count)) - (hidden - normal)


def export_fighter(files_root: Path, output_dir: Path, kind=0, costume_id=0, dol_path=Path("orig/GALE01/sys/main.dol"), symbols_path=Path("config/GALE01/symbols.txt"), *, archive_path=None, root_symbol=None, root_offset=None, copy_classes=None, reflection_preview=False, outline_groups=None, color_mask_preview=False):
    catalog = roster(files_root,include_extra=True) if kind>=27 else roster(files_root)
    fighter=next(f for f in catalog["fighters"] if f["fighter_kind"]==kind)
    costume=fighter["costumes"][costume_id]
    motions=json.loads(Path("build/melee_anim/motions.json").read_text())
    data_root=next(f for f in motions['normal_tables'] if f['fighter_kind']==kind)
    path = Path(archive_path) if archive_path else files_root / costume["file"]
    model = inspect_model(path, root_symbol or (costume["joint_symbol"] if root_offset is None else None), root_offset=root_offset)
    ar = Archive(path.read_bytes(), str(path))
    bones = model["joints"]
    worlds = world_matrices(bones)
    for bone, matrix in zip(bones, worlds):
        bone["world_bind_matrix"] = matrix.tolist()
    visibility = visibility_tables(files_root/data_root["fighter_archive"],data_root["fighter_root"],fighter["costume_count"]) if copy_classes is None else {
        'costumes':[{'classes':copy_classes,'script_texture_indices_to_global_tobj_indices':[]} for _ in fighter['costumes']]}
    groups=visibility["costumes"][costume_id]["classes"][0]["groups"]
    states=visibility_defaults(kind,costume_id,len(groups)) if copy_classes is None else [0 if group else -1 for group in groups]
    item_groups = outline_groups or []
    if kind == 24:
        # Source class 4 contains expanded outline meshes. Select its matching
        # alternatives with the same appearance states as the normal body.
        fighter_ar = Archive((files_root/data_root["fighter_archive"]).read_bytes())
        items = fighter_ar.pointer(fighter_ar.public(data_root["fighter_root"]) + 0x48)
        item_groups = visibility_lookup(fighter_ar, fighter_ar.pointer(items + 10 * 4), len(groups))
    selected = primary_drawables(len(model["drawables"]), visibility["costumes"][costume_id]["classes"], item_groups)
    outline_ids = {d for group in item_groups for option in group for d in option}
    selected.update(outline_ids)
    vis={"groups":groups,"defaults":states,"base":sorted(selected)}
    if item_groups:
        if len(item_groups)!=len(groups):raise FormatError('Outline/body visibility group counts differ')
        vis['outline_groups']=item_groups
    used_materials = {d["material"] for d in model["drawables"] if d["index"] in selected}
    material_ids, materials = {}, []
    animations = texture_animations(ar, model["root_symbol"])
    output_dir.mkdir(parents=True, exist_ok=True)
    images = {}

    def image_file(image, palette):
        w, h, fmt = ar.u16(image + 4), ar.u16(image + 6), ar.u32(image + 8)
        data = ar.read(ar.pointer(image), image_size(w, h, fmt))
        pal = ar.read(ar.pointer(palette), ar.u16(palette + 12) * 2) if palette is not None else None
        palfmt = ar.u32(palette + 4) if palette is not None else 1
        key = hashlib.sha256(struct.pack(">4I", w, h, fmt, palfmt) + data + (pal or b"")).hexdigest()[:20]
        filename = f"textures/{key}.png"
        if key not in images:
            pixels = decode_image(data, w, h, fmt, pal, palfmt)
            write_png(output_dir / filename, w, h, pixels)
            images[key] = {"file": filename, "width": w, "height": h, "format": fmt}
        return filename

    global_tobj = 0
    for material in model["materials"]:
        exported = dict(material)
        if copy_classes is not None:
            exported['copy_diffuse_only']=True
        if kind in (12,14,23,31):
            # Giga Bowser's leading bump stages are not diffuse RGB. Pikachu
            # and Pichu's eyes use COLORMAP_BLEND with blending=1: TObjMakeTExp
            # replaces the incoming RGB, rather than multiplying gray diffuse.
            exported['diffuse_texture_only']=True
        if kind == 14 or color_mask_preview:
            # Yoshi's cheek/belly markings are a second UV texture: source
            # TObjMakeTExp ALPHA_MASK interpolates RGB using texture alpha,
            # while ALPHAMAP_NONE preserves the opaque body coverage.
            exported['color_alpha_mask_layers'] = True
        if kind==13 or reflection_preview:
            exported['diffuse_texture_only']=True
            if any(t.get('flags',0)&15==1 for t in material['textures']):
                exported['reflection_texture_preview']=True
                if material['render_mode']&1:
                    exported['unlit']=True
        exported["textures"] = []
        for texture in material["textures"]:
            tex = texture["offset"]
            descriptor = dict(texture)
            descriptor.update({"global_tobj_index": global_tobj, "id": ar.u32(tex + 8),
                               "coordinate_type": ar.u32(tex + 64) & 15,
                               "rotation": list(struct.unpack(">3f", ar.read(tex + 16, 12))),
                               "scale": list(struct.unpack(">3f", ar.read(tex + 28, 12))),
                               "translation": list(struct.unpack(">3f", ar.read(tex + 40, 12))),
                               "repeat_s": ar.u8(tex + 60), "repeat_t": ar.u8(tex + 61),
                               "wrap_s": ar.u32(tex + 52), "wrap_t": ar.u32(tex + 56)})
            global_tobj += 1
            image, palette = ar.pointer(tex + 76), ar.pointer(tex + 80)
            animation = animations.get((material["offset"], descriptor["id"]))
            if animation is not None:
                from .ground_effects import aobj_tracks
                descriptor['animation_tracks']=[{'channel':t.channel,'startframe':t.startframe,
                    'frac_value':t.frac_value,'frac_slope':t.frac_slope,'data':t.data.hex()}
                    for t in aobj_tracks(ar, ar.pointer(animation+8), 0) if t.channel==1]
                values = aobj_frame0(ar, ar.pointer(animation + 8))
                table, palette_table = ar.pointer(animation + 12), ar.pointer(animation + 16)
                nimages, npalettes = ar.u16(animation + 20), ar.u16(animation + 22)
                descriptor["frame0_channels"] = values
                if table is not None:
                    image_descriptors = [ar.pointer(table + i * 4) for i in range(nimages)]
                    palette_descriptors = [ar.pointer(palette_table + i * 4) for i in range(npalettes)] if palette_table is not None else []
                    if 10 in values and palette_descriptors:
                        palette = palette_descriptors[int(values[10])]
                    descriptor["animation_images"] = [image_file(im, palette_descriptors[min(i,len(palette_descriptors)-1)] if palette_descriptors else palette) for i,im in enumerate(image_descriptors)]
                    if 1 in values:
                        image = image_descriptors[int(values[1])]
                        descriptor["initial_image_index"] = int(values[1])
            if image is not None:
                descriptor["image_file"] = image_file(image, palette)
            descriptor["texture_matrix"] = texture_matrix(descriptor).tolist()
            exported["textures"].append(descriptor)
        if material["offset"] in used_materials:
            material_ids[material["offset"]] = len(materials)
            materials.append(exported)
    meshes = []
    for polygon in model["polygons"]:
        if polygon["drawable_index"] not in selected:
            continue
        owner = bones[polygon["joint_index"]]
        if polygon["mode"] == "shape":raise FormatError("Shape-animation mesh not supported")
        mesh = decode_mesh(ar, polygon)
        mesh.update({"name": f"dobj_{polygon['drawable_index']:02d}_pobj_{polygon['index']:02d}",
                     "polygon_index": polygon["index"], "drawable_index": polygon["drawable_index"],
                     "material_index": material_ids[model["drawables"][polygon["drawable_index"]]["material"]],
                     "envelopes": polygon.get("envelopes") or [[{"joint_index":polygon["joint_index"],"weight":1.0}]]+([[{"joint_index":polygon["shared_joint_index"],"weight":1.0}]] if polygon.get("shared_joint_index") is not None else []), "owner_joint_index": polygon["joint_index"],
                     "cull_flags": polygon["flags"],
                     })
        if polygon['drawable_index'] in outline_ids:mesh['outline_pass']=True
        mesh["weights"]=[mesh["envelopes"][p] for p in mesh["palette_indices"]]
        positions, normals = skin_source_mesh(mesh, bones, worlds)
        mesh["positions_bind"], mesh["normals_bind"] = positions.tolist(), normals.tolist()
        meshes.append(mesh)
    all_positions = np.concatenate([np.asarray(m["positions_bind"]) for m in meshes])
    payload = {"schema": "melee_anim.model.v1", "matrix_convention": "row-major 4x4; column vectors; game axes Y up",
               "character": data_root["fighter_root"].removeprefix("ftData"), "fighter_kind": kind, "costume_id": costume_id,
               "source_archive": path.name, "source_sha256": model["archive_sha256"],
               "bones": bones, "meshes": meshes, "materials": materials, "images": list(images.values()),
               "bounds_bind": [all_positions.min(axis=0).tolist(), all_positions.max(axis=0).tolist()],
               "visibility": vis,
               "texture_script_map": visibility["costumes"][costume_id]["script_texture_indices_to_global_tobj_indices"],
               "limitations": ["Material TEV/reflection semantics retained as metadata; renderer implements them",
                               "No runtime props, effects, or fighter dynamic systems are evaluated"]}
    if kind==24:
        for material in materials:
            material["diffuse_rgba"]=catalog["game_watch"]["costume_rgba"][costume_id]
            material["alpha"]=1.0
            # PlGwNr materials use RENDER_CONSTANT (1), without DIFFUSE or
            # SPECULAR lighting. Preserve the costume's solid silhouette.
            material["unlit"]=True
        # ftGw_Init_OnLoad stores this in fp->x34_scale.z, but
        # Fighter_UpdateModelScale assigns it to the root JObj's LOCAL X.
        payload["runtime_root_scale"]=[catalog["game_watch"]["root_x_width"],1.0,1.0]
        payload["outline_rgba"]=catalog["game_watch"]["outline_rgba"]
    if outline_ids:
        payload['outline_geometry']=True
        # Keep materials separate: a source material can be shared by body
        # and outline drawables, but the outline pass applies a TEV overlay.
        color=payload.get('outline_rgba')
        if color is not None:
            configure_outline_materials(payload,color)
    if kind==32:
        payload['limitations'].append('Sandbag runtime RObj joint constraints/limits are not evaluated')
    target = output_dir / "model.json"
    target.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    return target, {"bones": len(bones), "meshes": len(meshes), "materials": len(materials),
                    "textures": len(images), "vertices": len(all_positions),
                    "triangles": sum(len(m["triangles"]) for m in meshes), "bounds_bind": payload["bounds_bind"]}


def configure_outline_materials(model, color):
    from .game_watch import outline_color
    cloned={}
    for mesh in model['meshes']:
        if not mesh.get('outline_pass'):continue
        index=mesh['material_index']
        if index not in cloned:
            material=dict(model['materials'][index])
            material.update(diffuse_rgba=outline_color(material['diffuse_rgba'],color),alpha=1.0,unlit=True,textures=[])
            cloned[index]=len(model['materials']);model['materials'].append(material)
        mesh['material_index']=cloned[index]


def export_mario(files_root,output_dir,costume_id=0,dol_path=Path("orig/GALE01/sys/main.dol"),symbols_path=Path("config/GALE01/symbols.txt")):
    return export_fighter(files_root,output_dir,0,costume_id,dol_path,symbols_path)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--costume", type=int, choices=range(5), default=0)
    parser.add_argument("--files-root", type=Path, default=Path("orig/GALE01/files"))
    parser.add_argument("--dol", type=Path, default=Path("orig/GALE01/sys/main.dol"))
    parser.add_argument("--symbols", type=Path, default=Path("config/GALE01/symbols.txt"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or Path("build/melee_anim/exported/mario") / f"costume_{args.costume:02d}"
    target, summary = export_mario(args.files_root, output, args.costume, args.dol, args.symbols)
    print(json.dumps({"model": str(target), **summary}, indent=2))


if __name__ == "__main__":
    main()
