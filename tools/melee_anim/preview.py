"""Render roster animation previews from extracted assets.

This CPU renderer uses NumPy and Pillow. It preserves source pose channels and
HSD envelope matrices, but approximates lighting/materials and does not run
the full fighter runtime, props, dynamics, audio, or the original results UI.
Optional Tech ground effects reproduce a focused subset of source effect data.
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
    effective = [{**b, "flags": b['flags'] if tree_type is None else (b["flags"] | 8 if tree_type & 1 else b["flags"] & ~8)
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
    if model.get("fighter_kind") == 24 or model.get('kirby_power')=='game-and-watch':
        return [0.0, math.pi/2 * (1 if action == "taunt" or action.startswith(('attack-','tech-','movement-')) else -1), 0.0]
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


def fit_knockdown_camera(cloud, view, size):
    """Center the visible fighter's whole-motion projected bounds, not effects."""
    center = (cloud.min(axis=0)+cloud.max(axis=0))/2
    projected = (cloud-center)@view
    lo, hi = projected.min(axis=0), projected.max(axis=0)
    offset = (lo+hi)/2
    offset[2] = 0
    center = center+view@offset
    extent = ((hi-lo)[:2]/2).max()
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


def projected_pose_center(posed, mask, view):
    visible = np.concatenate([p for (p, _), shown in zip(posed, mask) if shown]) @ view
    return view @ ((visible.min(0) + visible.max(0)) / 2)


def reflection_uv(normals, view):
    """HSD TEX_COORD_REFLECTION: camera normals map into the texture square.

    TObjSetupMtx uses +0.5 X, -0.5 Y and a 0.5 bias before the original
    texture SRT. Approximate the game's normal-matrix path for this preview.
    """
    n=np.asarray(normals,dtype=float)@view
    n/=np.maximum(np.linalg.norm(n,axis=-1,keepdims=True),1e-12)
    return np.stack((.5+.5*n[...,0],.5-.5*n[...,1]),axis=-1)


def render_frame(model, posed, textures, view, width, height, center, pixels_per_unit, background):
    color = np.empty((height, width, 4), dtype=np.uint8)
    color[:] = background
    depth = np.full((height, width), -np.inf)
    light = np.array([-0.35, 0.6, 0.72])
    light /= np.linalg.norm(light)
    ordered=list(zip(model['meshes'],posed))
    if any(m.get('item_alpha_blend') for m in model['materials']):
        ordered.sort(key=lambda pair:(bool(model['materials'][pair[0]['material_index']].get('item_alpha_blend')),
                                       np.mean((pair[1][0]-center)@view,axis=0)[2] if pair[1][0] is not None else 0))
    for mesh, (positions, normals) in ordered:
        if positions is None:
            continue
        projected = (positions - center) @ view
        screen = projected.copy()
        screen[:, 0] = projected[:, 0] * pixels_per_unit + width / 2
        screen[:, 1] = -projected[:, 1] * pixels_per_unit + height / 2
        material = model["materials"][mesh["material_index"]]
        rgba = np.array(material.get("diffuse_rgba") or [255, 255, 255, 255], dtype=float)
        candidates = [t for t in material["textures"] if t.get("coordinate_type", t.get("flags", 0) & 15) == 0]
        diffuse_only=material.get('copy_diffuse_only') or material.get('diffuse_texture_only')
        if diffuse_only:
            diffuse=[t for t in candidates if t.get('flags',0)&0x10]
            if diffuse:candidates=diffuse
        if not candidates and material.get('reflection_texture_preview'):
            candidates=[t for t in material['textures'] if t.get('coordinate_type',t.get('flags',0)&15)==1]
        base = next((t for t in candidates if ((t.get("flags", 0) >> 16) & 15) in (4, 5)),
                    candidates[0] if candidates else None)
        uv_set = str(max(0, base.get("source", 4)-4)) if base else "0"
        uvs = np.asarray(mesh.get("uv_sets", {}).get(uv_set, mesh["uvs"]), dtype=float)
        if base and base.get('coordinate_type',base.get('flags',0)&15)==1:
            uvs=reflection_uv(normals,view)
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
                replace_color=mode==5 or diffuse_only and mode==3 and base.get('blend',0)==1
                rgb = sampled if replace_color else rgb*sampled/255
            interpolated = (w0[..., None]*normals[ids[0]] + w1[..., None]*normals[ids[1]]
                            + w2[..., None]*normals[ids[2]])
            interpolated /= np.maximum(np.linalg.norm(interpolated, axis=2)[..., None], 1e-12)
            if not material.get("unlit"):
                shade = 0.6+0.4*np.maximum(0, interpolated @ light)
                rgb[..., :3] *= shade[..., None]
            output = color[ymin:ymax+1, xmin:xmax+1]
            if material.get('item_alpha_blend'):
                src_alpha=np.clip(rgb[...,3]*alpha/255,0,1)
                mask &= src_alpha>.001
                dst_alpha=output[...,3]/255
                out_alpha=src_alpha+dst_alpha*(1-src_alpha)
                combined=np.zeros_like(rgb)
                combined[...,:3]=(rgb[...,:3]*src_alpha[...,None]+output[...,:3]*dst_alpha[...,None]*(1-src_alpha[...,None]))/np.maximum(out_alpha[...,None],1e-8)
                combined[...,3]=out_alpha*255
                output[mask]=np.clip(np.rint(combined[mask]),0,255).astype('uint8')
            else:
                mask &= rgb[..., 3]*alpha >= 128
                output[mask] = np.clip(rgb[mask], 0, 255).astype(np.uint8)
                region[mask] = z[mask]
    return Image.fromarray(color)


def load_clip(report, action, section, files, kind=0, attack_catalog=Path('build/melee_anim/preview/attack-catalog.json')):
    if action.startswith(('attack-','tech-','movement-','other-')):
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
        if section=='wait' and action.startswith('victory'):
            entrance=table['motions'][aid-1]
            motion={**motion,'texture_initial_scripts':[(entrance.get('script',{}),entrance['frames'])]}
        outer=Archive((files/table["results_archive"]).read_bytes())
        base,length=outer.public_extent(table["motion_file_symbol"])
        data=outer.data[base:base+length]
    at,size=motion["offset"],motion["size"]
    archive=Archive(data[at:at+size],motion["symbol"])
    metadata,tracks=read_figatree(archive,motion["symbol"])
    if action.startswith(('attack-','tech-','movement-','other-')) and actor.get('character_prop'):
        motion={**motion,'character_prop':actor['character_prop']}
    if action.startswith('movement-') and actor.get('movement'):
        motion={**motion,'jump_actor':actor}
        metadata={**metadata,'frames':actor['render_duration']}
    if action.startswith('movement-') and actor.get('visibility_override'):
        motion={**motion,'visibility_override':actor['visibility_override']}
    if action.startswith('movement-') and actor.get('texture_initial_scripts'):
        motion={**motion,'texture_initial_scripts':actor['texture_initial_scripts']}
    if action.startswith(('attack-','tech-')) and actor.get('sequence'):
        motion={**motion,'sequence_actor':actor}
        metadata={**metadata,'frames':actor['render_duration']}
    if action.startswith('attack-'):
        from .character_effects import effect_archives
        if effect_archives(actor):motion={**motion,'effect_actor':actor}
        if actor.get('effect_loop_duration') and not actor.get('sequence'):
            motion={**motion,'fighter_period':metadata['frames']}
            metadata={**metadata,'frames':actor['effect_loop_duration']}
    return motion,metadata,tracks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("build/melee_anim/exported/mario/costume_00/model.json"))
    parser.add_argument("--companion", type=Path)
    parser.add_argument("--timeline", type=Path, help="edited 42-frame clapping-sync plan")
    parser.add_argument("--samples", type=Path, help="exact saved source times and whole-clip framing samples")
    parser.add_argument("--motions", type=Path, default=Path("build/melee_anim/motions.json"))
    parser.add_argument("--attack-catalog", type=Path, default=Path("build/melee_anim/preview/attack-catalog.json"))
    parser.add_argument('--ground-effects', choices=('on','off'), default='off', help='original tech flash/missed-tech ground burst')
    parser.add_argument('--kirby-power', default='none', help='copied character slug; none for ordinary Kirby')
    parser.add_argument('--center-jump', choices=('on','off'), default='off', help='follow the visible full/short-hop character with a fixed-scale camera')
    parser.add_argument("--files", type=Path, default=Path("orig/GALE01/files"))
    parser.add_argument("--action", default="results-clap", help="results-clap, victory1/2/3, taunt, or cataloged attack-/tech-<animation ID>")
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
    if args.ground_effects=='on' and not args.action.startswith('tech-'):
        parser.error('ground effects are only available for Tech animations')
    from .movement import centered_jump_setting
    try:
        center_jump = centered_jump_setting(args.action,args.center_jump)
    except ValueError as error:
        parser.error(str(error))
    model = json.loads(args.model.read_text())
    from .kirby_powers import validate_power
    validate_power('kirby' if model['fighter_kind']==4 else '',args.kirby_power)

    report = json.loads(args.motions.read_text())
    motion, metadata, tracks = load_clip(report, args.action, args.section, args.files,model["fighter_kind"], args.attack_catalog)
    hat=None;hat_path=None;power_info=None;model_folder=args.model.parent;render_model_path=args.model
    if model['fighter_kind']==4:
        from .kirby_powers import model_for_power, remap_tracks, reserved_parts
        repo=Path(__file__).resolve().parents[2]
        if args.kirby_power!='none':
            hat_path,power_info=model_for_power(repo,args.kirby_power,model['costume_id'])
            appearance=json.loads(hat_path.read_text())
            if power_info['body']:
                model=appearance;model_folder=hat_path.parent;render_model_path=hat_path
            else:
                hat=appearance
        tracks=remap_tracks(tracks,metadata['node_count'],len(model['bones']),reserved_parts(repo),model.get('kirby_part_mask',0))
        metadata={**metadata,'node_count':len(model['bones'])}
    if metadata["node_count"] != len(model["bones"]) or metadata["type"] not in (0, 1):
        parser.error("preview requires matching node hierarchy and supported scaling type")
    jump_scenes=None
    if motion.get('jump_actor'):
        from .movement import JumpScene
        mapper=(lambda ts,n:remap_tracks(ts,n,len(model['bones']),reserved_parts(repo),model.get('kirby_part_mask',0))) if model['fighter_kind']==4 else None
        jump_scenes={mode:JumpScene(motion['jump_actor'],args.files,mode,mapper) for mode in ('fullhop','shorthop')}
        jump_mode=motion['jump_actor']['movement']['mode']
    sequence_scene=None
    if motion.get('sequence_actor'):
        from .sequences import SequenceScene, SequenceProps, phase_drawables
        mapper=(lambda ts,n:remap_tracks(ts,n,len(model['bones']),reserved_parts(repo),model.get('kirby_part_mask',0))) if model['fighter_kind']==4 else None
        sequence_scene=SequenceScene(motion['sequence_actor'],args.files,mapper)
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
    textures = {t["image_file"]: np.asarray(Image.open(model_folder/t["image_file"]).convert("RGBA"))
                for m in model["materials"] for t in m["textures"] if t.get("image_file")}
    from .fighter_textures import FighterTextures
    face=FighterTextures(model,motion,model_folder,textures,sequence=sequence_scene)
    companion_face=None
    from .roster import visible_drawables
    movement_visibility=[]
    if args.action in ('movement-41','movement-42','movement-43') or (model['fighter_kind']==24 and args.action=='movement-207'):
        from .movement import movement_visibility_timeline
        movement_visibility=movement_visibility_timeline(model,motion)
    states=model.get("visibility",{}).get("defaults")
    if states is not None and not sequence_scene:
        states=states.copy()
        for group,value in motion.get('visibility_override',{}).items():states[int(group)]=value
        for command in motion.get("script",{}).get("commands",[]):
            if command["opcode"] in (1,2):break
            if "visibility_group" in command:
                i=command["visibility_group"]
                if 0<=i<len(states):states[i]=command["visibility_value"]
        visible=visible_drawables(model,states)
        if not movement_visibility:model["meshes"]=[m for m in model["meshes"] if m["drawable_index"] in visible]
    if hat:
        from .kirby_powers import attach_geometry
        visible=visible_drawables(hat)
        hat['meshes']=[m for m in hat['meshes'] if m['drawable_index'] in visible]
        offset=len(model['materials'])
        for material in hat['materials']:
            for texture in material['textures']:
                if texture.get('image_file'):
                    old=texture['image_file'];new='hat/'+old
                    textures[new]=np.asarray(Image.open(hat_path.parent/old).convert('RGBA'));texture['image_file']=new
        for mesh in hat['meshes']:mesh['material_index']+=offset
        model['materials'].extend(hat['materials'])
        hat_world=world_matrices(hat['bones'])
        hat_bind=[deform(mesh,hat_world,hat['bones']) for mesh in hat['meshes']]
    companion=None
    if args.companion:
        companion=json.loads(args.companion.read_text())
        cm,ct,ctracks=load_clip(report,args.action,args.section,args.files,companion["fighter_kind"], args.attack_catalog)
        companion_jumps={mode:JumpScene(cm['jump_actor'],args.files,mode) for mode in ('fullhop','shorthop')} if jump_scenes else None
        vis=visible_drawables(companion)
        if not sequence_scene:companion["meshes"]=[m for m in companion["meshes"] if m["drawable_index"] in vis]
        companion_sequence=SequenceScene(cm['sequence_actor'],args.files) if sequence_scene else None
        offset=len(model["materials"])
        for material in companion["materials"]:
            for texture in material["textures"]:
                if texture.get("image_file"):
                    old=texture["image_file"];new="companion/"+old
                    textures[new]=np.asarray(Image.open(args.companion.parent/old).convert("RGBA"));texture["image_file"]=new
        for mesh in companion["meshes"]:mesh["material_index"]+=offset
        companion_face=FighterTextures(companion,cm,args.companion.parent,textures,'companion/',companion_sequence)
        model["materials"].extend(companion["materials"])
    from .held_items import HeldItem, hold_joint, item_for_motion
    specification=motion.get('character_prop') or item_for_motion(args.action,model['fighter_kind'])
    held=None;companion_held=None
    if specification:
        held=HeldItem(args.files,specification,period,motion.get('script'))
        table=next(t for t in report['normal_tables'] if t['fighter_kind']==model['fighter_kind'])
        held_joint=hold_joint(args.files,table,model,Path(__file__).resolve().parents[2],specification)
        if specification.get('behavior')=='needle-release':
            held.anchor_at=lambda tick:pose_matrices(model['bones'],tracks,tick,metadata['type'],
                                                    root_scale=model.get('runtime_root_scale'),
                                                    root_rotation=runtime_root_rotation(model,args.action))[held_joint]
        def add_item_materials(item):
            offset=len(model['materials'])
            for mesh in item.model['meshes']:mesh['material_index']+=offset
            model['materials'].extend(item.model['materials']);textures.update(item.textures)
        add_item_materials(held)
        if companion:
            companion_held=HeldItem(args.files,specification,period,cm.get('script'))
            table=next(t for t in report['normal_tables'] if t['fighter_kind']==companion['fighter_kind'])
            companion_held_joint=hold_joint(args.files,table,companion,Path(__file__).resolve().parents[2],specification)
            add_item_materials(companion_held)
    view = camera_basis(args.yaw, args.pitch, args.roll)
    sequence_props=None;companion_sequence_props=None
    if sequence_scene:
        def matrices_at(scene,bones,tick,root_scale=None,root_rotation=None):
            meta,ts,time,_,_=scene.sample(tick)
            return pose_matrices(bones,ts,time,meta['type'],root_scale=root_scale,root_rotation=root_rotation)
        table=next(t for t in report['normal_tables'] if t['fighter_kind']==model['fighter_kind'])
        sequence_props=SequenceProps(sequence_scene,args.files,table,model,Path(__file__).resolve().parents[2],
            lambda tick:matrices_at(sequence_scene,model['bones'],tick,model.get('runtime_root_scale'),runtime_root_rotation(model,args.action)))
        def add_sequence_materials(props):
            offset=len(model['materials'])
            for mesh in props.meshes:mesh['material_index']+=offset
            model['materials'].extend(props.materials);textures.update(props.textures)
        add_sequence_materials(sequence_props)
        phase_visible=[phase_drawables(model,p) for _,_,p in sequence_scene.phases]
        if companion:
            table=next(t for t in report['normal_tables'] if t['fighter_kind']==companion['fighter_kind'])
            companion_sequence_props=SequenceProps(companion_sequence,args.files,table,companion,Path(__file__).resolve().parents[2],
                                                   lambda tick:matrices_at(companion_sequence,companion['bones'],tick))
            add_sequence_materials(companion_sequence_props)
            companion_phase_visible=[phase_drawables(companion,p) for _,_,p in companion_sequence.phases]
    def follow_center(posed,mask):
        return projected_pose_center(posed,mask,view)
    character_fx=None;companion_fx=None;effect_matrices={}
    if motion.get('effect_actor'):
        from .character_effects import CharacterEffects
        character_fx=CharacterEffects(motion['effect_actor'],args.files,model,sequence_scene)
        if companion and cm.get('effect_actor'):companion_fx=CharacterEffects(cm['effect_actor'],args.files,companion,companion_sequence)
    # Precompute poses once; fit over the whole selected source interval.
    cache = {}
    def evaluate_pose(frame,scene_mode=None):
        key = (round(frame, 10),scene_mode)
        if key in cache:
            return cache[key]
        pose_meta,pose_tracks,pose_time,height=jump_scenes[scene_mode or jump_mode].sample(frame) if jump_scenes else (metadata,tracks,frame,0.)
        if motion.get('fighter_period'):pose_time=frame%motion['fighter_period']
        if sequence_scene:pose_meta,pose_tracks,pose_time,phase_id,_=sequence_scene.sample(frame)
        matrices = pose_matrices(model["bones"], pose_tracks, pose_time, pose_meta["type"],
                                 root_scale=model.get("runtime_root_scale"),
                                 root_rotation=runtime_root_rotation(model, args.action))
        posed=[deform(mesh, matrices, model["bones"]) for mesh in model["meshes"]]
        shown = joint_visibility(model["bones"], pose_tracks, pose_time)
        mask = [shown[mesh["owner_joint_index"]] for mesh in model["meshes"]]
        if movement_visibility:
            state=next(state for time,state in reversed(movement_visibility) if time<=frame)
            visible=visible_drawables(model,state)
            mask=[active and mesh['drawable_index'] in visible for active,mesh in zip(mask,model['meshes'])]
        if sequence_scene:mask=[active and mesh['drawable_index'] in phase_visible[phase_id] for active,mesh in zip(mask,model['meshes'])]
        if hat:
            extra=attach_geometry(hat_bind,matrices[6],hat_world[0])
            posed.extend(extra)
            hat_shown=joint_visibility(hat['bones'],[],frame)
            mask.extend(shown[6] and hat_shown[mesh['owner_joint_index']] for mesh in hat['meshes'])
        if held:
            extra,visible=held.pose(matrices[held_joint],frame,view)
            posed.extend(extra);mask.extend(visible)
        if sequence_props:
            extra,visible=sequence_props.pose(matrices,frame,view)
            posed.extend(extra);mask.extend(visible)
        if height:
            for positions,_ in posed:positions[:,1]+=height
        if companion:
            cmeta,cts,ctime,cheight=companion_jumps[scene_mode or jump_mode].sample(frame) if jump_scenes else (ct,ctracks,frame%ct['frames'],0.)
            if sequence_scene:cmeta,cts,ctime,cphase_id,_=companion_sequence.sample(frame)
            cp=pose_matrices(companion["bones"],cts,ctime,cmeta["type"])
            extra=[deform(mesh,cp,companion["bones"]) for mesh in companion["meshes"]]
            for positions,normals in posed:positions[:,0]-=2.8
            for positions,normals in extra:positions[:,0]+=2.8;positions[:,1]+=cheight
            posed.extend(extra)
            shown = joint_visibility(companion["bones"], cts, ctime)
            mask.extend(shown[mesh["owner_joint_index"]] and (not sequence_scene or mesh['drawable_index'] in companion_phase_visible[cphase_id]) for mesh in companion["meshes"])
            if companion_held:
                extra,visible=companion_held.pose(cp[companion_held_joint],frame,view)
                for positions,_ in extra:positions[:,0]+=2.8
                posed.extend(extra);mask.extend(visible)
            if companion_sequence_props:
                extra,visible=companion_sequence_props.pose(cp,frame,view)
                for positions,_ in extra:positions[:,0]+=2.8
                posed.extend(extra);mask.extend(visible)
        if character_fx:
            fm=matrices.copy()
            if companion:fm[:,0,3]-=2.8
            effect_matrices[key]=(fm,None)
            if companion_fx:
                cfm=cp.copy();cfm[:,0,3]+=2.8
                effect_matrices[key]=(fm,cfm)
        cache[key] = (posed, mask)
        return posed, mask
    sampled = [evaluate_pose(frame) for frame in source_times]
    poses = [p for p, _ in sampled]
    visibility = [v for _, v in sampled]
    fitted = [evaluate_pose(frame)[0] for frame in fit_times] if fit_times else poses
    if jump_scenes:
        # Both heights use exactly the same geometry union/framing, so a short
        # hop does not look as tall as a full hop due to per-clip camera zoom.
        fitted=[]
        for mode in ('fullhop','shorthop'):
            duration=max(jump_scenes[mode].duration,companion_jumps[mode].duration if companion else 0)
            count=max(1,math.ceil(duration/args.ticks_per_second*args.fps))
            for i in range(count+1):
                geometry,mask=evaluate_pose(duration*i/count,mode)
                offset=follow_center(geometry,mask) if center_jump else np.zeros(3)
                fitted.append([(p-offset,n) for (p,n),shown in zip(geometry,mask) if shown] if center_jump else geometry)
    # Capture fit exclusions before extending the fixed renderer mesh list.
    sequence_fit_mask=None
    if sequence_scene:
        sequence_fit_mask=[True]*(len(model['meshes'])+(len(hat['meshes']) if hat else 0))
        sequence_fit_mask.extend(not released for released in sequence_props.release_meshes)
        if companion:
            sequence_fit_mask.extend([True]*len(companion['meshes']))
            sequence_fit_mask.extend(not released for released in companion_sequence_props.release_meshes)
    if hat:model['meshes'].extend(hat['meshes'])
    if held:model['meshes'].extend(held.model['meshes'])
    if sequence_props:model['meshes'].extend(sequence_props.meshes)
    if companion:model["meshes"].extend(companion["meshes"])
    if companion_held:model['meshes'].extend(companion_held.model['meshes'])
    if companion_sequence_props:model['meshes'].extend(companion_sequence_props.meshes)
    framing = fitted if jump_scenes else fitted+poses if fit_times else poses
    knockdown = args.action.startswith('tech-')
    if sequence_scene:
        cloud=np.concatenate([p for frame,mask in sampled for (p,_),shown,fit in zip(frame,mask,sequence_fit_mask) if shown and fit])
        emitted=sequence_props.emission_geometry(view)
        if companion_sequence_props:emitted.extend(p+np.array([2.8,0,0]) for p in companion_sequence_props.emission_geometry(view))
        if emitted:cloud=np.concatenate([cloud]+emitted)
    elif knockdown or movement_visibility:
        fit_samples = [evaluate_pose(t) for t in (fit_times or source_times)]
        cloud = np.concatenate([p for frame, mask in fit_samples for (p,_),shown in zip(frame,mask) if shown])
    else:
        fit_count=len(model['meshes'])-len(held.model['meshes']) if held and specification.get('behavior')=='needle-release' else len(model['meshes'])
        cloud = np.concatenate([p for frame in framing for p, _ in frame[:fit_count]])
        if held and specification.get('behavior')=='needle-release':
            # Keep the muzzle/spawn point in view without shrinking the fighter
            # to fit the entire free-flight distance of every emitted needle.
            tick=specification['shot_ticks'][0]
            spawned,shown=held.pose(held.anchor_at(tick),tick,view)
            cloud=np.concatenate([cloud]+[p for (p,_),visible in zip(spawned,shown) if visible])
    if character_fx:
        bounds=[]
        for tick in fit_times or source_times:
            fm,cfm=effect_matrices[(round(tick,10),None)]
            bounds.extend(character_fx.bounds(tick,fm,view))
            if companion_fx:bounds.extend(companion_fx.bounds(tick,cfm,view))
        if bounds:cloud=np.concatenate([cloud]+bounds)
    effect = None
    flash = None
    anchors = [[-2.8,0,0],[2.8,0,0]] if companion else [[0,0,0]]
    if knockdown:
        from .techs import ground_effect
        from .ground_effects import GroundEffect
        effect_kind = ground_effect(args.action)
        if effect_kind:
            effect = GroundEffect(args.files,effect_kind)
    # Keep one center/scale for the whole clip. Knockdown centers the fighter
    # in the selected view, then fits the complete visible impact at that pivot.
    center, scale = (fit_knockdown_camera if knockdown or center_jump else fit_camera)(cloud, view, args.size)
    if effect and args.ground_effects=='on':
        bounds = effect.visible_bounds(fit_times or source_times,anchors,view)
        if len(bounds):
            extent = max(np.abs((cloud-center)@view)[:,:2].max(),
                         np.abs((bounds-center)@view)[:,:2].max())
            scale = args.size*.88/(2*extent)
    if knockdown:
        from .fighter_colors import TechFlash, tech_color_animation
        if tech_color_animation(args.action) is not None:
            flash = TechFlash(args.files,args.action,motion)
    images = []
    raster=None
    if args.backend=="native":
        from .native_raster import NativeRaster
        raster=NativeRaster(args.size)
        print(f"Offscreen raster: {raster.renderer}",flush=True)
    started = time.monotonic()
    for i, pose in enumerate(poses):
        face.apply(source_times[i])
        if companion_face:companion_face.apply(source_times[i])
        drawn = [p if shown else (None, None) for p, shown in zip(pose, visibility[i])]
        frame_center=center+follow_center(pose,visibility[i]) if center_jump else center
        image = (raster.render if raster else render_frame)(model, drawn, textures, view, args.size, args.size, frame_center, scale, (34, 38, 46, 0))
        if flash:
            image = flash.apply(image,source_times[i])
        if effect and args.ground_effects=='on':
            layer = effect.render(source_times[i],anchors,view,args.size,center,scale)
            image = Image.alpha_composite(layer,image)
        if character_fx:
            fm,cfm=effect_matrices[(round(source_times[i],10),None)]
            image=character_fx.render(source_times[i],fm,view,args.size,frame_center,scale,image)
            if companion_fx:image=companion_fx.render(source_times[i],cfm,view,args.size,frame_center,scale,image)
        image.save(args.output/f"frame_{i:04d}.png")
        images.append(image.convert("RGBA"))
        if i == 0 or (i+1) % 20 == 0 or i == len(poses)-1:
            print(f"Rendered {i+1}/{len(poses)} frames ({time.monotonic()-started:.1f}s)", flush=True)
    from .gif_export import encode_frames, quantize_rgba
    frames = quantize_rgba(images)
    (args.output/'preview.gif').write_bytes(encode_frames(frames,[1000//args.fps]*len(frames),
                                            0 if (looping and not args.max_frames) or sync_plan else None))
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
                "transparent_background": True, "alpha_source": "raster coverage; GIF threshold 128; RGBA PNG master",
                "camera_pitch": args.pitch, "camera_roll": args.roll,
                "camera_rotation_order": "Ry(yaw) @ Rx(pitch) @ Rz(roll)",
                "runtime_root_scale": model.get("runtime_root_scale"),
                "runtime_root_rotation": runtime_root_rotation(model, args.action),
                "camera_center": center.tolist(), "camera_pixels_per_unit": scale,
                "model_sha256": hashlib.sha256(render_model_path.read_bytes()).hexdigest(),
                "render_backend": args.backend,
                "limitations": ["Approximate paired placement" if companion else "Isolated fighter", "no complete gameplay scripts/props/particles/dynamics/audio",
                                "approximate materials/lighting/reflection", "source finger seam preserved",
                                "no rendered game-reference validation yet"]}
    if held:
        manifest['held_item']={**held.provenance(),'fighter_hold_joint':held_joint,
                              'companion_hold_joint':companion_held_joint if companion_held else None}
        manifest['framing_policy']='whole-animation fighter and held-item geometry'
        if specification.get('behavior')=='needle-release':manifest['framing_policy']='stable fighter and emission-point fit; needles leave the image naturally'
    if character_fx:
        manifest['character_effects']=character_fx.provenance()
        manifest['fighter_loop_period_ticks']=motion.get('fighter_period')
        manifest['effect_loop_policy']='repeat original fighter/effect cycles over their least common multiple' if motion.get('fighter_period') else 'phase-local effect timing'
        manifest['framing_policy']='whole-animation fighter and attached effect geometry; foreground RGBA effects'
    if knockdown:
        manifest['ground_effects_enabled'] = bool(effect and args.ground_effects=='on')
        manifest['ground_effect'] = effect.provenance() if effect else None
        manifest['effect_anchors'] = anchors if effect else []
        manifest['ground_effect_display_scale'] = 1.0 if effect else None
        manifest['framing_policy'] = ('fighter-centered whole-motion fit with complete visible impact alpha; shared source scale'
                                      if manifest['ground_effects_enabled'] else 'visible fighter-only projected whole-motion bounds')
        manifest['fighter_flash'] = flash.provenance() if flash else None
    if model['fighter_kind']==4:
        manifest['kirby_power']=args.kirby_power
        manifest['kirby_appearance']=None if power_info is None else {
            'archive':power_info['archive'].name,'body_archive':power_info['body'].name if power_info['body'] else None,
            'archive_sha256':hashlib.sha256(power_info['archive'].read_bytes()).hexdigest(),
            'appearance_model_sha256':hashlib.sha256(hat_path.read_bytes()).hexdigest(),
            'body_archive_sha256':hashlib.sha256(power_info['body'].read_bytes()).hexdigest() if power_info['body'] else None,
            'attachment_part':6 if hat else None,'reserved_part_mask':power_info['mask'],
            'limitations':['Hat dynamics remain at bind pose; copied projectiles, items and complete runtime scripts are not executed']}
    if motion.get('visibility_override'):
        manifest['visibility_override']=motion['visibility_override']
    if movement_visibility:manifest['movement_visibility_timeline']=movement_visibility
    if jump_scenes:
        manifest['movement_scenario']=jump_scenes[jump_mode].provenance()
        manifest['center_jump_enabled']=center_jump
        manifest['framing_policy']=('follow projected visible fighter center; fixed scale shared across full/short hops'
                                    if center_jump else 'shared complete full-hop and short-hop geometry bounds')
        if center_jump:manifest['camera_sample_centers']=[(center+follow_center(p,v)).tolist() for p,v in sampled]
        if companion:manifest['companion_movement_scenario']=companion_jumps[jump_mode].provenance()
    if sequence_scene:
        manifest['sequence']=sequence_scene.provenance()
        manifest['sequence_props']=sequence_props.provenance()
        manifest['framing_policy']='stable whole-sequence visible geometry; outgoing needles leave the image'
        if companion:manifest['companion_sequence']=companion_sequence.provenance()
    if sync_plan:
        manifest['sync_plan'] = sync_plan
        manifest['output_mode'] = 'clapping-sync alteration'
        manifest['uniform_gif_ticks'] = True
        manifest['companion_sha256'] = hashlib.sha256(args.companion.read_bytes()).hexdigest() if args.companion else None
    manifest['fighter_texture_commands']='source opcode 40, frozen TObj image FObjs; costume-specific mapping'
    manifest_path=args.output/'preview-manifest.json'
    temporary=manifest_path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    temporary.replace(manifest_path)
    print(f"Preview: {args.output/'preview.gif'}", flush=True)


if __name__ == "__main__":
    main()
