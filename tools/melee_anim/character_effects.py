"""Source-attached special effects with original meshes, colors and curves.

Foreground RGBA compositing approximates GX depth/additive blending. This
does not evaluate particle generators or simulate a reflection/absorption.
"""
from copy import deepcopy
import math
from pathlib import Path
import struct

import numpy as np
from PIL import Image

from .ground_effects import GroundEffect, rgba_triangles


def character_effects(kind, name):
    def effect(file,table,index,gfx,label,joint,**extra):
        return [dict(source_archive=file,table=table,descriptor_id=index,gfx_id=gfx,
                     name=label,raw_joint=joint,**extra)]
    if kind in (1,22) and name in ('SpecialLwStart','SpecialAirLwStart','SpecialLwLoop','SpecialAirLwLoop','SpecialLwHit','SpecialAirLwHit'):
        phase='start' if name.endswith('Start') else 'hold' if name.endswith('Loop') else 'hit'
        index={'hold':0,'start':1,'hit':2}[phase]
        return effect('EfFxData.dat','effFoxDataTable',index,1160+index,'Reflector',4,phase=phase,
                      loop_period_ticks=6 if phase=='hold' else None)
    if kind in (0,21,17) and name in ('SpecialLw','SpecialAirLw'):
        luigi=kind==17
        return effect('EfLgData.dat' if luigi else 'EfMrData.dat','effLuigiDataTable' if luigi else 'effMarioDataTable',
                      1,1289 if luigi else 1148,'Luigi Cyclone' if luigi else 'Tornado',0,
                      phase='air' if name=='SpecialAirLw' else 'ground',cyclone=True)
    if kind==8 and name in ('SpecialLwHold','SpecialAirLwHold','SpecialLwHit','SpecialAirLwHit'):
        return effect('EfNsData.dat','effNessDataTable',2,1264,'PSI Magnet',23,phase='hold',loop_period_ticks=40)
    return []


def effect_archives(actor):
    effects=list(actor.get('character_effects') or [])
    for phase in actor.get('sequence',{}).get('phases',[]):
        effects.extend(phase.get('character_effects') or [])
    return {e['source_archive'] for e in effects}


def shared_loop_period(body_period,effects):
    periods=[body_period]+[e['loop_period_ticks'] for e in effects if e.get('loop_period_ticks')]
    if any(not math.isfinite(p) or p<=0 or int(p)!=p for p in periods):
        raise ValueError('Shared effect loops require positive integer game-tick periods')
    return math.lcm(*(int(p) for p in periods))


def animation_time(tick, end, loop):
    return tick % end if loop and end>0 else min(tick,end) if end>0 else tick


class TimedTrack:
    def __init__(self,track,timing):
        self.track=track;self.timing=timing
    def __getattr__(self,name):
        return getattr(self.track,name)
    def evaluate(self,tick):
        return self.track.evaluate(animation_time(tick,*self.timing))


def effect_pixels(pixels, tex, blend, diffuse, alpha):
    """Original full BLEND color/alpha maps; preserve partial coverage."""
    rgb=pixels[:,:,:3]/255
    tev=tex.get('tev_bytes')
    if tev and int.from_bytes(tev[28:32],'big')&0x40000000:
        # The selected effects all use C0*(1-texture)+KONST*texture.
        rgb=np.asarray(list(tev[20:23]))/255*(1-rgb)+np.asarray(list(tev[16:19]))/255*rgb
    out=np.empty_like(pixels,dtype=float)
    blend=np.clip(blend,0,1)
    out[:,:,:3]=np.asarray(diffuse)/255*(1-blend)+rgb*blend
    out[:,:,3]=alpha*(1-blend)+pixels[:,:,3]/255*blend
    return np.rint(np.clip(out,0,1)*255).astype('uint8')


def composite_effect(destination,source,additive=False):
    if not additive:return Image.alpha_composite(destination,source)
    dst=np.asarray(destination,dtype=float)/255;src=np.asarray(source,dtype=float)/255
    alpha=src[:,:,3]+dst[:,:,3]*(1-src[:,:,3])
    light=np.clip(dst[:,:,:3]*dst[:,:,3,None]+src[:,:,:3]*src[:,:,3,None],0,1)
    rgb=np.divide(light,alpha[:,:,None],out=np.zeros_like(light),where=alpha[:,:,None]>0)
    return Image.fromarray(np.rint(np.clip(np.dstack([rgb,alpha]),0,1)*255).astype('uint8'))


class AttachedEffect(GroundEffect):
    def __init__(self,files,specification):
        super().__init__(files,'attached',descriptor=specification)
        self.specification=specification
        self.preserve_billboard_roll=True
        self.source_lifetime=self.lifetime
        # efLib_Create truncates the lifetime; 0.1 means no timer, not 0.1
        # ticks. Each AObj independently loops/clamps its authored curves.
        self.lifetime=math.floor(self.lifetime) or math.inf
        self.tracks=[TimedTrack(t,self.track_timing[id(t)]) for t in self.tracks]
        self.material_tracks={k:[TimedTrack(t,self.track_timing[id(t)]) for t in ts] for k,ts in self.material_tracks.items()}
        self.tex_tracks={k:[TimedTrack(t,self.track_timing[id(t)]) for t in ts] for k,ts in self.tex_tracks.items()}
        from .hsd import Archive
        ar=Archive((Path(files)/specification['source_archive']).read_bytes())
        for material in self.materials.values():
            pe=material['pixel_engine']
            material['additive']=bool(pe is not None and ar.u8(pe+4)==1 and ar.u8(pe+5)==4 and ar.u8(pe+6)==1)
            for tex in material['textures']:
                at=tex['offset']
                tex.update(rotation=list(struct.unpack('>3f',ar.read(at+16,12))),
                           scale=list(struct.unpack('>3f',ar.read(at+28,12))),
                           translation=list(struct.unpack('>3f',ar.read(at+40,12))),
                           repeat_s=ar.u8(at+60),repeat_t=ar.u8(at+61),wrap_s=ar.u32(at+52),wrap_t=ar.u32(at+56),
                           tev_bytes=ar.read(tex['tev'],32) if tex['tev'] else None)
        if specification.get('cyclone') and specification['phase']=='ground':
            # efLib_Cb_ftMr/ftLg_SpecialLw hides the second root child on
            # ground, and its descendants. Air shows both source branches.
            children=[b['index'] for b in self.bones if b['parent']==0]
            hidden={children[1]} if len(children)>1 else set()
            for bone in self.bones:
                if bone['parent'] in hidden:hidden.add(bone['index'])
            self.meshes=[m for m in self.meshes if m['owner'] not in hidden]

    def geometry(self,tick,anchor,view):
        # Position-only RObj attachment. Retain source/billboard orientation;
        # uniform scale comes from fighter root Y, never the animated hip.
        origin,scale=anchor
        return [(m,p*scale+origin) for m,p in super().geometry(tick,[0,0,0],view)]

    def render(self,tick,anchors,view,size,center,scale,background=None):
        from .export_model import texture_matrix
        from .preview import texture_uv
        layer=background.copy() if background is not None else Image.new('RGBA',(size,size))
        for anchor in anchors:
            for mesh,positions in self.geometry(tick,anchor,view):
                mat=self.materials[mesh['material']]
                values={t.channel:t.evaluate(tick) for t in self.material_tracks.get(mat['offset'],[])}
                diffuse=[values.get(4+i,mat['diffuse_rgba'][i]/255)*255 for i in range(3)]
                alpha=values.get(10,mat['alpha'])
                colors=np.asarray(mesh['colors'],dtype=float).copy()
                uvs=np.asarray(mesh['uvs'],dtype=float)
                if mat['textures']:
                    tex=deepcopy(mat['textures'][0])
                    tv={t.channel:t.evaluate(tick) for t in self.tex_tracks.get((mat['offset'],tex['id']),[])}
                    for channel,key,axis in [(2,'translation',0),(3,'translation',1),(4,'scale',0),(5,'scale',1),(6,'rotation',0),(7,'rotation',1),(8,'rotation',2)]:
                        if tv.get(channel) is not None:tex[key][axis]=tv[channel]
                    tex['texture_matrix']=texture_matrix(tex)
                    uvs=texture_uv(uvs,tex)
                    images=self.tex_images.get((mat['offset'],tex['id']))
                    if images:
                        index=int(tv.get(1,0))
                        if not 0<=index<len(images):raise ValueError('Effect image index is outside its source table')
                        source_pixels=images[index]
                    else:source_pixels=self.textures[tex['offset']]
                    pixels=effect_pixels(source_pixels,tex,tv.get(9,tex['blend']),diffuse,alpha)
                else:
                    rgb=[255]*3 if mat['render_mode']&3==2 else diffuse
                    pixels=np.array([[[*rgb,alpha*255]]],dtype='uint8')
                projected=(positions-center)@view
                projected[:,0]=size/2+projected[:,0]*scale
                projected[:,1]=size/2-projected[:,1]*scale
                part=rgba_triangles(size,projected,uvs,colors,mesh['triangles'],pixels)
                layer=composite_effect(layer,part,mat['additive'])
        return layer

    def provenance(self):
        return {**self.specification,'source_sha256':self.archive_sha256,'source_lifetime':self.source_lifetime,
                'particle_channels_omitted':len(self.particle_channels),
                'limitations':['Foreground compositing approximates GX depth; additive RGB uses union coverage for transparent exports',
                               'Particle generators, collisions, reflected projectiles and absorption are not simulated']}


class CharacterEffects:
    def __init__(self,actor,files,model,scene=None):
        self.scene=scene;self.entries=[]
        phases=actor['sequence']['phases'] if scene else [actor]
        for index,phase in enumerate(phases):
            for spec in phase.get('character_effects') or []:
                if spec['raw_joint']>=len(model['bones']):raise ValueError('Effect attachment is outside fighter skeleton')
                self.entries.append((index,spec['raw_joint'],AttachedEffect(files,spec)))

    def active(self,tick,matrices):
        phase,elapsed=self.scene.sample(tick)[3:] if self.scene else (0,tick)
        root_scale=np.linalg.norm(matrices[0][:3,1])
        return [(effect,elapsed,(matrices[joint][:3,3],root_scale)) for index,joint,effect in self.entries if index==phase]

    def bounds(self,tick,matrices,view):
        return [p for effect,time,anchor in self.active(tick,matrices) for _,p in effect.geometry(time,anchor,view)]

    def render(self,tick,matrices,view,size,center,scale,background=None):
        layer=background.copy() if background is not None else Image.new('RGBA',(size,size))
        for effect,time,anchor in self.active(tick,matrices):
            layer=effect.render(time,[anchor],view,size,center,scale,layer)
        return layer

    def provenance(self):
        return [{'phase_index':index,**effect.provenance()} for index,_,effect in self.entries]
