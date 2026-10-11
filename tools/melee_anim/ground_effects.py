"""Original EfCoData tech/ground-burst meshes and curves, with alpha compositing.

This focused effect preview supports source joint visibility/SRT, vertex colors,
textures and animated texture blend/TEV colors. It approximates GX TEV blending,
billboards and layering; it does not run the game's particle generator VM.
"""
from pathlib import Path

import numpy as np
from PIL import Image

from .hsd import Archive, FormatError
from .inspect_models import inspect_model, linked
from .export_model import decode_mesh, world_matrices
from .motions import Track
from .texture import decode_image, image_size

EFFECT_IDS = {'missed': (1030, 4), 'tech': (1053, 15)}


def aobj_tracks(ar, at, index):
    if at is None:
        return []
    tracks = []
    for f in linked(ar, ar.pointer(at+8), 0):
        t = Track(index, ar.u8(f+12), int(ar.f32(f+8)), ar.u8(f+13), ar.u8(f+14),
                  ar.read(ar.pointer(f+16), ar.u32(f+4)))
        t.packets()
        tracks.append(t)
    return tracks


def matched_tree(ar, bones, root, visit):
    """Match descriptor child/next topology to preorder joints with bounds."""
    by_parent = {}
    for b in bones:
        by_parent.setdefault(b['parent'], []).append(b['index'])
    visited = set()
    def walk(at, parent):
        indices = by_parent.get(parent, [])
        for index in indices:
            if at is None:
                return
            if at in visited:
                raise FormatError('Effect animation tree repeats a node')
            visited.add(at)
            visit(index, at)
            walk(ar.pointer(at), index)
            at = ar.pointer(at+4)
        if at is not None:
            raise FormatError('Effect animation tree exceeds model topology')
    walk(root, None)


def rgba_triangles(size, positions, uvs, colors, triangles, pixels):
    """Orthographic textured triangle layer; straight RGBA, no baked matte."""
    out = np.zeros((size,size,4),dtype=float)
    for tri in triangles:
        p = positions[tri,:2]; uv = uvs[tri]; col = colors[tri]
        lo = np.maximum(np.floor(p.min(axis=0)).astype(int),0)
        hi = np.minimum(np.ceil(p.max(axis=0)).astype(int),size-1)
        if np.any(lo>hi):
            continue
        a,b,c = p
        det = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(det)<1e-8:
            continue
        yy,xx = np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
        x,y = xx+.5,yy+.5
        w0 = ((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/det
        w1 = ((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/det
        w2 = 1-w0-w1
        inside = (w0>=-1e-7)&(w1>=-1e-7)&(w2>=-1e-7)
        weights = np.stack([w0,w1,w2],axis=-1)
        coords = weights@uv
        # The two original effect textures clamp at their edges.
        u = np.clip(np.rint(coords[:,:,0]*(pixels.shape[1]-1)).astype(int),0,pixels.shape[1]-1)
        v = np.clip(np.rint(coords[:,:,1]*(pixels.shape[0]-1)).astype(int),0,pixels.shape[0]-1)
        sample = pixels[v,u]/255*(weights@col)
        sample[:,:,3] *= inside
        region = out[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
        # Adjacent triangles describe one surface, not overlapping particles.
        replace = sample[:,:,3]>region[:,:,3]
        region[replace] = sample[replace]
    return Image.fromarray(np.clip(out*255,0,255).astype('uint8'))


class GroundEffect:
    def __init__(self, files, kind):
        self.kind = kind
        self.gfx_id, self.descriptor_id = EFFECT_IDS[kind]
        path = Path(files)/'EfCoData.dat'
        ar = Archive(path.read_bytes(),str(path))
        desc = ar.public('effCommonDataTable')+8+20*self.descriptor_id
        self.lifetime = ar.f32(desc)
        source = inspect_model(path,root_offset=ar.pointer(desc+4))
        self.archive_sha256 = source['archive_sha256']
        self.bones = source['joints']
        self.tracks = []
        self.particle_channels = []
        def joints(index, node):
            for track in aobj_tracks(ar,ar.pointer(node+8),index):
                if track.channel == 40:
                    self.particle_channels.append(track)
                elif track.channel not in (1,2,3,5,6,7,8,9,10,11,12):
                    raise FormatError(f'Unsupported effect joint channel {track.channel}')
                else:
                    self.tracks.append(track)
        matched_tree(ar,self.bones,ar.pointer(desc+8),joints)
        self.material_tracks, self.tex_tracks = {}, {}
        def materials(index,node):
            dobjs = list(linked(ar,self.bones[index]['dobj'],4))
            anims = list(linked(ar,ar.pointer(node+8),0))
            if len(anims)>len(dobjs):
                raise FormatError('Effect material animation exceeds drawables')
            for dobj,anim in zip(dobjs,anims):
                mat = ar.pointer(dobj+8)
                self.material_tracks[mat] = aobj_tracks(ar,ar.pointer(anim+4),0)
                for ta in linked(ar,ar.pointer(anim+8),0):
                    if ar.u16(ta+20) or ar.u16(ta+22):
                        raise FormatError('Effect image/palette swapping requires support')
                    self.tex_tracks[(mat,ar.u32(ta+4))] = aobj_tracks(ar,ar.pointer(ta+8),0)
        matched_tree(ar,self.bones,ar.pointer(desc+12),materials)
        self.materials = {m['offset']:m for m in source['materials']}
        self.textures = {}
        for mat in self.materials.values():
            for tex in mat['textures']:
                off = tex['offset']; image = ar.pointer(off+76); pal = ar.pointer(off+80)
                tex['id'] = ar.u32(off+8)
                tex['konst'] = list(ar.read(tex['tev']+16,4)) if tex['tev'] else [255]*4
                w,h,fmt = ar.u16(image+4),ar.u16(image+6),ar.u32(image+8)
                palette = ar.read(ar.pointer(pal),ar.u16(pal+12)*2) if pal is not None else None
                pixels = decode_image(ar.read(ar.pointer(image),image_size(w,h,fmt)),w,h,fmt,palette,ar.u32(pal+4) if pal is not None else 1)
                self.textures[off] = np.frombuffer(pixels,dtype='uint8').reshape(h,w,4)
        self.meshes = []
        for poly in source['polygons']:
            if poly['mode']!='rigid_or_shared':
                raise FormatError('Ground effect requires unsupported mesh deformation')
            mesh = decode_mesh(ar,poly)
            mesh.update(owner=poly['joint_index'], material=source['drawables'][poly['drawable_index']]['material'])
            self.meshes.append(mesh)

    def geometry(self, tick, anchor, view):
        from .preview import joint_visibility
        if tick<0 or tick>=self.lifetime:
            return []
        poses = [{k:list(b[k]) for k in ('rotation','scale','position')} for b in self.bones]
        # efLib_Create_Attach_Pos replaces the root translation with TopN's
        # world position at entry. Ground is flat in this isolated preset.
        poses[0]['position'] = list(anchor)
        for t in self.tracks:
            v=t.evaluate(tick)
            if v is None:continue
            key,axis = ('rotation',t.channel-1) if t.channel<=3 else ('position',t.channel-5) if t.channel<=7 else ('scale',t.channel-8) if t.channel<=10 else (None,None)
            if key:poses[t.joint_index][key][axis]=.001 if key=='scale' and abs(v)<.001 else v
        matrices = world_matrices(self.bones,poses)
        shown = joint_visibility(self.bones,self.tracks,tick)
        result = []
        for mesh in self.meshes:
            i = mesh['owner']
            if not shown[i]:continue
            local = np.asarray(mesh['source_positions'])
            matrix = matrices[i].copy()
            # Rotation billboard: approximate camera-facing orientation while
            # retaining world center/animated scale. Exact GX billboards remain
            # a reference-comparison task.
            if self.bones[i]['flags']&0xE00:
                matrix[:3,:3] = view@np.diag(np.linalg.norm(matrix[:3,:3],axis=0))
            points = local@matrix[:3,:3].T+matrix[:3,3]
            result.append((mesh,points))
        return result

    def render(self, tick, anchors, view, size, center, scale):
        layer = Image.new('RGBA',(size,size))
        for anchor in anchors:
            for mesh,positions in self.geometry(tick,anchor,view):
                mat = self.materials[mesh['material']]; tex = mat['textures'][0]
                values = {t.channel:t.evaluate(tick) for t in self.tex_tracks.get((mat['offset'],tex['id']),[])}
                tint = np.asarray(tex['konst'],dtype=float)/255
                for channel in range(12,16):
                    if values.get(channel) is not None:tint[channel-12]=values[channel]
                colors = np.asarray(mesh['colors'],dtype=float)
                pixels = self.textures[tex['offset']].astype(float)/255
                # Both descriptors use color A=texture0, B=konst,
                # C=texture, D=zero. GX ADD evaluates (1-C)*A+C*B.
                # Taking raw texel RGB as the final color produces a spurious
                # neon-green missed-tech burst.
                combined = pixels[:,:,:3]*(1-pixels[:,:,:3])+pixels[:,:,:3]*tint[:3]
                blend = np.clip(values.get(9,tex['blend']),0,1)
                if self.kind=='tech':
                    pixels[:,:,:3] = (1-blend)+combined*blend
                    pixels[:,:,3] *= blend
                else:
                    pixels[:,:,:3] = combined
                    colors[:,3] *= tint[3]
                projected = (positions-center)@view
                projected[:,0] = size/2+projected[:,0]*scale
                projected[:,1] = size/2-projected[:,1]*scale
                part = rgba_triangles(size,projected,np.asarray(mesh['uvs']),colors,mesh['triangles'],np.clip(pixels*255,0,255).astype('uint8'))
                layer = Image.alpha_composite(layer,part)
        return layer

    def provenance(self):
        return {'source_archive':'EfCoData.dat','source_sha256':self.archive_sha256,'gfx_id':self.gfx_id,'descriptor_id':self.descriptor_id,
                'lifetime_ticks':self.lifetime,'spawn_tick':0,'floor':'flat, horizontal',
                'limitations':['Approximate TEV/billboard/layer compositing; no particle VM, quake or audio',
                               'Missed-tech particle/dust effect 1031 and surface-specific overrides not evaluated',
                               'Effect is clipped to the selected character motion interval']}
