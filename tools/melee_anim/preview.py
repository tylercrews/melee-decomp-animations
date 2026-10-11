"""Render roster animation previews from extracted assets.

This CPU renderer uses NumPy and Pillow. It preserves source pose channels and
HSD envelope matrices, but approximates lighting/materials and does not run
fighter scripts, effects, props, dynamics, audio, or the original results UI.
Blender remains the planned production renderer. Outputs stay under build/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
from PIL import Image, ImageDraw

from .hsd import Archive
from .motions import read_figatree
from .export_model import local_matrix, skin_source_mesh, world_matrices


def srt_matrix(rotation, scale, position):
    """Uncompensated local HSD SRT, exposed for small reference checks."""
    return local_matrix(rotation, scale, position)


def pose_matrices(bones, tracks, source_frame, tree_type=1, *, root_scale=None, root_rotation=None):
    rotation = np.array([b["rotation"] for b in bones], dtype=float)
    scale = np.array([b["scale"] for b in bones], dtype=float)
    position = np.array([b["position"] for b in bones], dtype=float)
    if any(b["flags"] & ((1 << 17) | (1 << 24) | (1 << 25)) for b in bones):
        raise ValueError("Preview pilot does not support quaternion/independent matrices")
    for track in tracks:
        value = track.evaluate(source_frame)
        if value is None:
            continue
        i, channel = track.joint_index, track.channel
        if i >= len(bones):
            raise ValueError("Animation exceeds pilot joint hierarchy")
        if channel in (1, 2, 3):
            rotation[i, channel - 1] = value
        elif channel in (5, 6, 7):
            position[i, channel - 5] = value
        elif channel in (8, 9, 10):
            scale[i, channel - 8] = .001 if abs(value)<.001 else value
        elif channel in (11,12):
            continue  # HSD node/branch visibility is handled before drawing.
        else:
            raise ValueError(f"Preview does not support side-effect joint channel {channel}")
    # Fighter_UpdateModelScale and ftPartSetRotY act on TopN before HSD
    # builds the hierarchy/palette. A post-skin world-axis squash loses this
    # rotation/scale order and gives Game & Watch the wrong silhouette.
    if root_scale is not None:
        scale[0] = root_scale
    if root_rotation is not None:
        rotation[0] = root_rotation
    # lbAnim sets/clears classical scaling from FigaTree.type. Results use
    # type 1, while Mario's gameplay taunt uses type 0.
    animated = {t.joint_index for t in tracks}
    effective = [{**b, "flags": (b["flags"] | 8 if tree_type & 1 else b["flags"] & ~8)
                  if i in animated else b["flags"]}
                 for i, b in enumerate(bones)]
    poses = [{"rotation": rotation[i], "scale": scale[i], "position": position[i]}
             for i in range(len(bones))]
    return np.asarray(world_matrices(effective, poses))


def runtime_root_rotation(model, action):
    """Game & Watch's source runtime facing, separate from camera orbit.

    gm_8017A67C selects -1 for results; the standard right-facing taunt uses
    +1. Fighter initialization / ftDemo_SetFacingDirection use pi/2*facing.
    Other fighters retain the existing isolated source-clip presentation.
    """
    if model.get("fighter_kind") == 24:
        return [0.0, math.pi/2 * (1 if action == "taunt" or action.startswith('attack-') else -1), 0.0]
    return None


def deform(mesh, matrices, bones):
    """Evaluate retained GX source coordinates by their exact HSD palette."""
    return skin_source_mesh(mesh, bones, matrices)


def joint_visibility(bones, tracks, source_frame):
    """HSD_A_J_NODE/BRANCH update JOBJ_HIDDEN; hiding a node keeps its children.

    The joint array is parent-before-child. Branch tracks affect the subtree,
    and later child tracks may override their own visibility, as in HSD.
    """
    visible = [not (b["flags"] & (1 << 4)) for b in bones]
    for track in tracks:
        if track.channel not in (11, 12):
            continue
        value = track.evaluate(source_frame)
        if value is None:
            continue
        node = track.joint_index
        if not 0 <= node < len(bones):
            raise ValueError("Visibility animation exceeds joint hierarchy")
        visible[node] = value > .5
        if track.channel == 12:
            subtree = {node}
            for i in range(node + 1, len(bones)):
                if bones[i]["parent"] in subtree:
                    subtree.add(i)
                    visible[i] = value > .5
    return visible


def camera_basis(yaw, pitch=0, roll=0):
    """Camera-to-world basis: Ry(yaw) @ Rx(pitch) @ Rz(roll), degrees.

    Orbit the camera, keeping source poses and world lighting unchanged.
    Row-vector world coordinates are projected by multiplying this basis.
    """
    if not all(math.isfinite(a) for a in (yaw, pitch, roll)):
        raise ValueError('Camera angles must be finite')
    x, y, z = map(math.radians, (pitch, yaw, roll))
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return ry @ rx @ rz


def fit_camera(cloud, view, size):
    """Fit all sampled geometry around a camera-independent world pivot."""
    center = (cloud.min(axis=0)+cloud.max(axis=0))/2
    projected = (cloud-center) @ view
    extent = np.abs(projected[:, :2]).max()
    if extent <= 0:
        raise ValueError('Cannot frame degenerate geometry')
    return center, size*.82/(2*extent)


def texture_uv(uv, descriptor):
    """HSD UV transform followed by GX clamp/repeat/mirrored repeat."""
    if descriptor.get("texture_matrix") is not None:
        matrix = np.asarray(descriptor["texture_matrix"], dtype=float)
        coords = np.concatenate((uv, np.ones((*uv.shape[:-1], 2))), axis=-1)
        uv = (coords @ matrix.T)[..., :2]
    else:
        uv = uv.copy()
    for axis, field in enumerate(("wrap_s", "wrap_t")):
        mode = descriptor.get(field, 1)
        if mode == 0:
            uv[..., axis] = np.clip(uv[..., axis], 0, 1-1e-10)
        elif mode == 1:
            uv[..., axis] %= 1
        elif mode == 2:
            value = uv[..., axis] % 2
            uv[..., axis] = np.minimum(np.where(value > 1, 2-value, value), 1-1e-10)
        else:
            raise ValueError(f"Unsupported GX wrap mode {mode}")
    return uv


def render_frame(model, posed, textures, view, width, height, center, pixels_per_unit, background):
    color = np.empty((height, width, 4), dtype=np.uint8)
    color[:] = background
    depth = np.full((height, width), -np.inf)
    light = np.array([-0.35, 0.6, 0.72])
    light /= np.linalg.norm(light)
    for mesh, (positions, normals) in zip(model["meshes"], posed):
        if positions is None:
            continue
        projected = (positions - center) @ view
        screen = projected.copy()
        screen[:, 0] = projected[:, 0] * pixels_per_unit + width / 2
        screen[:, 1] = -projected[:, 1] * pixels_per_unit + height / 2
        material = model["materials"][mesh["material_index"]]
        rgba = np.array(material.get("diffuse_rgba") or [255, 255, 255, 255], dtype=float)
        candidates = [t for t in material["textures"] if t.get("coordinate_type", t.get("flags", 0) & 15) == 0]
        base = next((t for t in candidates if ((t.get("flags", 0) >> 16) & 15) in (4, 5)),
                    candidates[0] if candidates else None)
        uv_set = str(max(0, base.get("source", 4)-4)) if base else "0"
        uvs = np.asarray(mesh.get("uv_sets", {}).get(uv_set, mesh["uvs"]), dtype=float)
        texture = textures.get(base["image_file"]) if base else None
        alpha = float(material.get("alpha", 1.0))
        for triangle in mesh["triangles"]:
            ids = np.asarray(triangle, dtype=int)
            a, b, c = screen[ids]
            area = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(area) < 1e-9:
                continue
            # Screen Y is inverted; GX clockwise fronts have positive area.
            cull = mesh.get("cull_flags", 0) & 0xC000
            if cull == 0xC000 or cull == 0x4000 and area > 0 or cull == 0x8000 and area < 0:
                continue
            xmin, ymin = np.floor(screen[ids, :2].min(axis=0)).astype(int)
            xmax, ymax = np.ceil(screen[ids, :2].max(axis=0)).astype(int)
            xmin, xmax = max(0, xmin), min(width-1, xmax)
            ymin, ymax = max(0, ymin), min(height-1, ymax)
            if xmin > xmax or ymin > ymax:
                continue
            yy, xx = np.mgrid[ymin:ymax+1, xmin:xmax+1]
            xx, yy = xx + 0.5, yy + 0.5
            w0 = ((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/area
            w1 = ((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/area
            w2 = 1-w0-w1
            z = w0*a[2]+w1*b[2]+w2*c[2]
            region = depth[ymin:ymax+1, xmin:xmax+1]
            mask = (w0 >= -1e-8) & (w1 >= -1e-8) & (w2 >= -1e-8) & (z > region)
            if not mask.any():
                continue
            rgb = np.broadcast_to(rgba, (*mask.shape, 4)).copy()
            if texture is not None:
                uv = w0[..., None]*uvs[ids[0]] + w1[..., None]*uvs[ids[1]] + w2[..., None]*uvs[ids[2]]
                uv = texture_uv(uv, base)
                tx = np.minimum((uv[..., 0]*texture.shape[1]).astype(int), texture.shape[1]-1)
                ty = np.minimum((uv[..., 1]*texture.shape[0]).astype(int), texture.shape[0]-1)
                sampled = texture[ty, tx].astype(float)
                mode = (base.get("flags", 0) >> 16) & 15
                rgb = sampled if mode == 5 else rgb*sampled/255
            interpolated = (w0[..., None]*normals[ids[0]] + w1[..., None]*normals[ids[1]]
                            + w2[..., None]*normals[ids[2]])
            interpolated /= np.maximum(np.linalg.norm(interpolated, axis=2)[..., None], 1e-12)
            if not material.get("unlit"):
                shade = 0.6+0.4*np.maximum(0, interpolated @ light)
                rgb[..., :3] *= shade[..., None]
            mask &= rgb[..., 3]*alpha >= 128
            output = color[ymin:ymax+1, xmin:xmax+1]
            output[mask] = np.clip(rgb[mask], 0, 255).astype(np.uint8)
            region[mask] = z[mask]
    return Image.fromarray(color)


def load_clip(report, action, section, files, kind=0, attack_catalog=Path('build/melee_anim/preview/attack-catalog.json')):
    if action.startswith('attack-'):
        from .attacks import find_action
        actor = find_action(json.loads(attack_catalog.read_text()), kind, action)
        motion = actor['clip']
        data = (files/actor['animation_file']).read_bytes()
    elif action == "taunt":
        table=next(x for x in report["taunts"] if x["fighter_kind"]==kind)
        chosen=table["standard_facing"]["right"]
        motion=next(c for c in table["clips"] if c["animation_id"]==chosen["animation_id"] and c["source_fighter_kind"]==chosen["source_fighter_kind"])
        source=next(x for x in report["taunts"] if x["fighter_kind"]==chosen["source_fighter_kind"])
        data=(files/source["animation_file"]).read_bytes()
    else:
        table=next(x for x in report["results"] if x["fighter_kind"]==kind)
        aid={"results-clap":9,"victory1":0,"victory2":2,"victory3":5}[action]
        if section=="wait" and action.startswith("victory"):aid+=1
        motion=table["motions"][aid]
        outer=Archive((files/table["results_archive"]).read_bytes())
        base,length=outer.public_extent(table["motion_file_symbol"])
        data=outer.data[base:base+length]
    at,size=motion["offset"],motion["size"]
    archive=Archive(data[at:at+size],motion["symbol"])
    metadata,tracks=read_figatree(archive,motion["symbol"])
    return motion,metadata,tracks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("build/melee_anim/exported/mario/costume_00/model.json"))
    parser.add_argument("--companion", type=Path)
    parser.add_argument("--timeline", type=Path, help="edited 42-frame clapping-sync plan")
    parser.add_argument("--samples", type=Path, help="exact saved source times and whole-clip framing samples")
    parser.add_argument("--motions", type=Path, default=Path("build/melee_anim/motions.json"))
    parser.add_argument("--attack-catalog", type=Path, default=Path("build/melee_anim/preview/attack-catalog.json"))
    parser.add_argument("--files", type=Path, default=Path("orig/GALE01/files"))
    parser.add_argument("--action", default="results-clap", help="results-clap, victory1/2/3, taunt, or cataloged attack-<animation ID>")
    parser.add_argument("--section", choices=("source", "wait"), default="source")
    parser.add_argument("--output", type=Path, default=Path("build/melee_anim/preview/mario_clap"))
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--fps", type=int, default=50, choices=(25, 50))
    parser.add_argument("--ticks-per-second", type=float, default=60)
    parser.add_argument("--yaw", type=float, default=0)
    parser.add_argument("--pitch", type=float, default=0)
    parser.add_argument("--roll", type=float, default=0)
    parser.add_argument("--backend", choices=("python","native"), default="python")
    parser.add_argument("--max-frames", type=int, help="diagnostic truncation, not a complete export")
    args = parser.parse_args()
    if not 64 <= args.size <= 1024 or args.ticks_per_second <= 0:
        parser.error("size must be 64..1024 and ticks-per-second positive")
    if args.max_frames is not None and args.max_frames <= 0:
        parser.error("max-frames must be positive")
    if args.section == "wait" and not args.action.startswith("victory"):
        parser.error("wait sections are only available for victory actions")
    if not all(math.isfinite(v) for v in (args.yaw, args.pitch, args.roll)):
        parser.error('camera angles must be finite')
    if args.samples and (args.timeline or args.max_frames):
        parser.error('samples cannot be combined with timeline or truncation')
    model = json.loads(args.model.read_text())

    report = json.loads(args.motions.read_text())
    motion, metadata, tracks = load_clip(report, args.action, args.section, args.files,model["fighter_kind"], args.attack_catalog)
    if metadata["node_count"] != len(model["bones"]) or metadata["type"] not in (0, 1):
        parser.error("preview requires matching node hierarchy and supported scaling type")
    period = metadata["frames"]
    looping = motion.get("effective_loop", motion.get("motion_loop", False))
    count = max(1, math.ceil(period/args.ticks_per_second*args.fps))
    source_times = [period*i/count for i in range(count)]
    if not looping:
        source_times.append(period)
    sync_plan = None
    fit_times = None
    if args.samples:
        saved = json.loads(args.samples.read_text())
        source_times = saved['source_times']
        fit_times = saved['fit_source_times']
        if (saved['fps'] != args.fps or not source_times or not fit_times or
                any(not math.isfinite(t) or not 0 <= t <= period for t in source_times+fit_times)):
            parser.error('invalid saved sample timing')
    if args.timeline:
        sync_plan = json.loads(args.timeline.read_text())
        if args.action != 'results-clap' or args.section != 'source' or args.max_frames:
            parser.error('sync timelines require complete clapping exports')
        source_times = sync_plan['source_times']
        fit_times = sync_plan['fit_source_times']
        if (sync_plan['fps'] != args.fps or sync_plan['length'] != 42 or len(source_times) != 42 or
                any(not math.isfinite(t) or not 0 <= t < period for t in source_times+fit_times)):
            parser.error('invalid clapping-sync timing')
    if args.max_frames:
        source_times = source_times[:args.max_frames]
    args.output.mkdir(parents=True, exist_ok=True)
    expected_frames = {f"frame_{i:04d}.png" for i in range(len(source_times))}
    stale = {p.name for p in args.output.glob("frame_*.png")} - expected_frames
    if stale:
        parser.error(f"Output has extra frame files; choose a fresh output directory: {sorted(stale)[:5]}")
    textures = {t["image_file"]: np.asarray(Image.open(args.model.parent/t["image_file"]).convert("RGBA"))
                for m in model["materials"] for t in m["textures"] if t.get("image_file")}
    from .roster import visible_drawables
    states=model.get("visibility",{}).get("defaults")
    if states is not None:
        states=states.copy()
        for command in motion.get("script",{}).get("commands",[]):
            if command["opcode"] in (1,2):break
            if "visibility_group" in command:
                i=command["visibility_group"]
                if 0<=i<len(states):states[i]=command["visibility_value"]
        visible=visible_drawables(model,states)
        model["meshes"]=[m for m in model["meshes"] if m["drawable_index"] in visible]
    companion=None
    if args.companion:
        companion=json.loads(args.companion.read_text())
        cm,ct,ctracks=load_clip(report,args.action,args.section,args.files,companion["fighter_kind"], args.attack_catalog)
        vis=visible_drawables(companion)
        companion["meshes"]=[m for m in companion["meshes"] if m["drawable_index"] in vis]
        offset=len(model["materials"])
        for material in companion["materials"]:
            for texture in material["textures"]:
                if texture.get("image_file"):
                    old=texture["image_file"];new="companion/"+old
                    textures[new]=np.asarray(Image.open(args.companion.parent/old).convert("RGBA"));texture["image_file"]=new
        for mesh in companion["meshes"]:mesh["material_index"]+=offset
        model["materials"].extend(companion["materials"])
    view = camera_basis(args.yaw, args.pitch, args.roll)
    # Precompute poses once; fit over the whole selected source interval.
    cache = {}
    def evaluate_pose(frame):
        key = round(frame, 10)
        if key in cache:
            return cache[key]
        matrices = pose_matrices(model["bones"], tracks, frame, metadata["type"],
                                 root_scale=model.get("runtime_root_scale"),
                                 root_rotation=runtime_root_rotation(model, args.action))
        posed=[deform(mesh, matrices, model["bones"]) for mesh in model["meshes"]]
        shown = joint_visibility(model["bones"], tracks, frame)
        mask = [shown[mesh["owner_joint_index"]] for mesh in model["meshes"]]
        if companion:
            cp=pose_matrices(companion["bones"],ctracks,frame%ct["frames"],ct["type"])
            extra=[deform(mesh,cp,companion["bones"]) for mesh in companion["meshes"]]
            for positions,normals in posed:positions[:,0]-=2.8
            for positions,normals in extra:positions[:,0]+=2.8
            posed.extend(extra)
            shown = joint_visibility(companion["bones"], ctracks, frame % ct["frames"])
            mask.extend(shown[mesh["owner_joint_index"]] for mesh in companion["meshes"])
        cache[key] = (posed, mask)
        return posed, mask
    sampled = [evaluate_pose(frame) for frame in source_times]
    poses = [p for p, _ in sampled]
    visibility = [v for _, v in sampled]
    fitted = [evaluate_pose(frame)[0] for frame in fit_times] if fit_times else poses
    if companion:model["meshes"].extend(companion["meshes"])
    framing = fitted+poses if fit_times else poses
    cloud = np.concatenate([p for frame in framing for p, _ in frame])
    # One world-space pivot for the entire animation, independent of camera
    # angles. Symmetric projected bounds retain the pivot without clipping.
    center, scale = fit_camera(cloud, view, args.size)
    images = []
    raster=None
    if args.backend=="native":
        from .native_raster import NativeRaster
        raster=NativeRaster(args.size)
        print(f"Offscreen raster: {raster.renderer}",flush=True)
    started = time.monotonic()
    for i, pose in enumerate(poses):
        drawn = [p if shown else (None, None) for p, shown in zip(pose, visibility[i])]
        image = (raster.render if raster else render_frame)(model, drawn, textures, view, args.size, args.size, center, scale, (34, 38, 46, 255))
        image.save(args.output/f"frame_{i:04d}.png")
        images.append(image.convert("RGB"))
        if i == 0 or (i+1) % 20 == 0 or i == len(poses)-1:
            print(f"Rendered {i+1}/{len(poses)} frames ({time.monotonic()-started:.1f}s)", flush=True)
    # One shared palette avoids per-frame palette shimmer in this diagnostic.
    tile = Image.new("RGB", (args.size*min(8, len(images)), args.size))
    for i in range(min(8, len(images))):
        tile.paste(images[i*len(images)//min(8, len(images))], (i*args.size, 0))
    palette = tile.quantize(colors=256)
    frames = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in images]
    options = {"save_all": True, "append_images": frames[1:], "duration": 1000//args.fps, "disposal": 2}
    if looping and not args.max_frames:
        options["loop"] = 0
    if sync_plan:
        from .gif_export import encode_frames
        (args.output/'preview.gif').write_bytes(encode_frames(frames, [1000//args.fps]*len(frames), 0))
    else:
        frames[0].save(args.output/"preview.gif", **options)
    if raster:raster.close()
    strip = Image.new("RGB", (args.size*4, args.size+28), (34, 38, 46))
    draw = ImageDraw.Draw(strip)
    for i in range(4):
        frame_id = min(len(images)-1, i*len(images)//4)
        strip.paste(images[frame_id], (i*args.size, 28))
        draw.text((i*args.size+8, 8), f"source frame {source_times[frame_id]:.2f}", fill="white")
    strip.save(args.output/"contact_sheet.png")
    manifest = {"prototype": "Roster textured pose preview; approximate shading and runtime behavior",
                "character": model["character"], "costume_id": model["costume_id"],
                "source_model_archive": model["source_archive"],
                "action": args.action, "section": args.section, "source_symbol": motion["symbol"],
                "source_period_frames": period, "authored_loop": looping, "sample_source_times": source_times,
                "fps": args.fps, "nominal_ticks_per_second": args.ticks_per_second,
                "timing_basis": "explicit prototype preset; not measured emulator timing",
                "output_duration_seconds": len(images)/args.fps,
                "complete_interval": args.max_frames is None, "size": args.size, "camera_yaw": args.yaw,
                "camera_pitch": args.pitch, "camera_roll": args.roll,
                "camera_rotation_order": "Ry(yaw) @ Rx(pitch) @ Rz(roll)",
                "runtime_root_scale": model.get("runtime_root_scale"),
                "runtime_root_rotation": runtime_root_rotation(model, args.action),
                "camera_center": center.tolist(), "camera_pixels_per_unit": scale,
                "model_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
                "render_backend": args.backend,
                "limitations": ["Approximate paired placement" if companion else "Isolated fighter", "no gameplay scripts/props/effects/dynamics/audio",
                                "approximate materials/lighting/reflection", "source finger seam preserved",
                                "no rendered game-reference validation yet"]}
    if sync_plan:
        manifest['sync_plan'] = sync_plan
        manifest['output_mode'] = 'clapping-sync alteration'
        manifest['uniform_gif_ticks'] = True
        manifest['companion_sha256'] = hashlib.sha256(args.companion.read_bytes()).hexdigest() if args.companion else None
    (args.output/"preview-manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(f"Preview: {args.output/'preview.gif'}", flush=True)


if __name__ == "__main__":
    main()
