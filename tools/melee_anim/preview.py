"""Render a first Mario animation preview from extracted assets.

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


def pose_matrices(bones, tracks, source_frame, tree_type=1):
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
            scale[i, channel - 8] = value
        else:
            raise ValueError(f"Preview does not support side-effect joint channel {channel}")
    # lbAnim sets/clears classical scaling from FigaTree.type. Results use
    # type 1, while Mario's gameplay taunt uses type 0.
    animated = {t.joint_index for t in tracks}
    effective = [{**b, "flags": (b["flags"] | 8 if tree_type & 1 else b["flags"] & ~8)
                  if i in animated else b["flags"]}
                 for i, b in enumerate(bones)]
    poses = [{"rotation": rotation[i], "scale": scale[i], "position": position[i]}
             for i in range(len(bones))]
    return np.asarray(world_matrices(effective, poses))


def deform(mesh, matrices, bones):
    """Evaluate retained GX source coordinates by their exact HSD palette."""
    return skin_source_mesh(mesh, bones, matrices)


def camera_basis(yaw):
    angle = math.radians(yaw)
    forward = np.array([math.sin(angle), 0.0, math.cos(angle)])
    right = np.array([math.cos(angle), 0.0, -math.sin(angle)])
    return np.stack((right, np.array([0.0, 1.0, 0.0]), forward), axis=1)


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
            shade = 0.6+0.4*np.maximum(0, interpolated @ light)
            rgb[..., :3] *= shade[..., None]
            mask &= rgb[..., 3]*alpha >= 128
            output = color[ymin:ymax+1, xmin:xmax+1]
            output[mask] = np.clip(rgb[mask], 0, 255).astype(np.uint8)
            region[mask] = z[mask]
    return Image.fromarray(color)


def load_clip(report, action, section, files):
    if action == "taunt":
        choices = [x for x in report["mario_gameplay_examples"] if x["animation_id"] == 239]
        motion = choices[0]
        data = (files / "PlMrAJ.dat").read_bytes()
    else:
        table = next(x for x in report["results"] if x["fighter_root"] == "ftDataMario")
        animation_id = {"results-clap": 9, "victory1": 0, "victory2": 2, "victory3": 5}[action]
        if section == "wait" and action.startswith("victory"):
            animation_id += 1
        motion = table["motions"][animation_id]
        outer = Archive((files / table["results_archive"]).read_bytes())
        data = outer.data[table["motion_file_data_offset"]:]
    at, size = motion["offset"], motion["size"]
    archive = Archive(data[at:at+size], motion["symbol"])
    metadata, tracks = read_figatree(archive, motion["symbol"])
    return motion, metadata, tracks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("build/melee_anim/exported/mario/costume_00/model.json"))
    parser.add_argument("--motions", type=Path, default=Path("build/melee_anim/motions.json"))
    parser.add_argument("--files", type=Path, default=Path("orig/GALE01/files"))
    parser.add_argument("--action", choices=("results-clap", "victory1", "victory2", "victory3", "taunt"), default="results-clap")
    parser.add_argument("--section", choices=("source", "wait"), default="source")
    parser.add_argument("--output", type=Path, default=Path("build/melee_anim/preview/mario_clap"))
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--fps", type=int, default=50, choices=(25, 50))
    parser.add_argument("--ticks-per-second", type=float, default=60)
    parser.add_argument("--yaw", type=float, default=0)
    parser.add_argument("--max-frames", type=int, help="diagnostic truncation, not a complete export")
    args = parser.parse_args()
    if not 64 <= args.size <= 1024 or args.ticks_per_second <= 0:
        parser.error("size must be 64..1024 and ticks-per-second positive")
    if args.max_frames is not None and args.max_frames <= 0:
        parser.error("max-frames must be positive")
    if args.section == "wait" and not args.action.startswith("victory"):
        parser.error("wait sections are only available for victory actions")
    model = json.loads(args.model.read_text())
    if model.get("character", "mario").lower() != "mario":
        parser.error("This pilot only supports the verified Mario rig")
    report = json.loads(args.motions.read_text())
    motion, metadata, tracks = load_clip(report, args.action, args.section, args.files)
    if metadata["node_count"] != len(model["bones"]) or metadata["type"] not in (0, 1):
        parser.error("pilot requires the matching Mario node hierarchy and supported scaling type")
    period = metadata["frames"]
    looping = motion.get("effective_loop", motion.get("motion_loop", False))
    count = max(1, math.ceil(period/args.ticks_per_second*args.fps))
    source_times = [period*i/count for i in range(count)]
    if not looping:
        source_times.append(period)
    if args.max_frames:
        source_times = source_times[:args.max_frames]
    args.output.mkdir(parents=True, exist_ok=True)
    textures = {t["image_file"]: np.asarray(Image.open(args.model.parent/t["image_file"]).convert("RGBA"))
                for m in model["materials"] for t in m["textures"] if t.get("image_file")}
    view = camera_basis(args.yaw)
    # Precompute poses once; fit over the whole selected source interval.
    poses = []
    for frame in source_times:
        matrices = pose_matrices(model["bones"], tracks, frame, metadata["type"])
        poses.append([deform(mesh, matrices, model["bones"]) for mesh in model["meshes"]])
    cloud = np.concatenate([p for frame in poses for p, _ in frame])
    projected = cloud @ view
    low, high = projected.min(axis=0), projected.max(axis=0)
    center = ((low+high)/2) @ view.T
    scale = args.size*0.82/max(high[0]-low[0], high[1]-low[1])
    images = []
    started = time.monotonic()
    for i, pose in enumerate(poses):
        image = render_frame(model, pose, textures, view, args.size, args.size, center, scale, (34, 38, 46, 255))
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
    frames[0].save(args.output/"preview.gif", **options)
    strip = Image.new("RGB", (args.size*4, args.size+28), (34, 38, 46))
    draw = ImageDraw.Draw(strip)
    for i in range(4):
        frame_id = min(len(images)-1, i*len(images)//4)
        strip.paste(images[frame_id], (i*args.size, 28))
        draw.text((i*args.size+8, 8), f"source frame {source_times[frame_id]:.2f}", fill="white")
    strip.save(args.output/"contact_sheet.png")
    manifest = {"prototype": "Mario CPU textured pose preview; approximate shading, scripts not executed",
                "action": args.action, "section": args.section, "source_symbol": motion["symbol"],
                "source_period_frames": period, "authored_loop": looping, "sample_source_times": source_times,
                "fps": args.fps, "nominal_ticks_per_second": args.ticks_per_second,
                "timing_basis": "explicit prototype preset; not measured emulator timing",
                "output_duration_seconds": len(images)/args.fps,
                "complete_interval": args.max_frames is None, "size": args.size, "camera_yaw": args.yaw,
                "model_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
                "limitations": ["Mario rig only", "no gameplay scripts/props/effects/dynamics/audio",
                                "approximate materials/lighting/reflection", "source finger seam preserved",
                                "no rendered game-reference validation yet"]}
    (args.output/"preview-manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(f"Preview: {args.output/'preview.gif'}", flush=True)


if __name__ == "__main__":
    main()
