"""Original common particle 416 for sleeping results poses.

Focused bytecode/texture support for this verified emitter, not a particle VM.
Spawn origins are snapshots; source tornado motion uses a deterministic seed.
"""
import hashlib
import math
from pathlib import Path
import struct

import numpy as np
from PIL import Image

from .hsd import Archive, FormatError
from .held_items import script_events
from .texture import decode_image, image_size
from .ground_effects import rgba_triangles


def bubble_spawns(motion):
    return [(tick,c['gfx_spawn']) for tick,c in script_events(motion.get('script',{}),motion['frames'])
            if c.get('gfx_spawn',{}).get('gfx_id')==416]


def particle_samples(program,life,initial_size):
    try:return _particle_samples(program,life,initial_size)
    except (IndexError,struct.error) as error:raise FormatError('Truncated sleep particle command') from error


def _particle_samples(program,life,initial_size):
    """Decode this particle's waits, image, size and PrimEnv color commands."""
    pc=0;wait=0;size=float(initial_size);pose=0
    colors=[np.array([255.]*4),np.zeros(4)];targets=[c.copy() for c in colors];remaining=[0,0]
    size_target=size;size_remaining=0;samples=[]
    def count():
        nonlocal pc
        value=program[pc];pc+=1
        if value&128:value=((value&127)<<8)+program[pc];pc+=1
        return value
    for tick in range(life):
        if size_remaining:size+=(size_target-size)/size_remaining;size_remaining-=1
        for i in range(2):
            if remaining[i]:colors[i]+=(targets[i]-colors[i])/remaining[i];remaining[i]-=1
        if wait:wait-=1
        if not wait:
            for _ in range(256):
                op=program[pc];pc+=1
                if op<128:
                    wait=op&31
                    if op&32:wait=(wait<<8)+program[pc];pc+=1
                    if op&64:pose=program[pc];pc+=1
                    if wait:break
                elif op==0xA0:
                    size_remaining=count();size_target=struct.unpack_from('>f',program,pc)[0];pc+=4
                    if not math.isfinite(size_target) or size_target<0:raise FormatError('Invalid sleep particle size')
                    if not size_remaining:size=size_target
                elif op&0xF0 in (0xC0,0xD0):
                    index=0 if op&0xF0==0xC0 else 1;remaining[index]=count();targets[index]=colors[index].copy()
                    for channel in range(4):
                        if op&(1<<channel):targets[index][channel]=program[pc];pc+=1
                    if not remaining[index]:colors[index]=targets[index].copy()
                elif op==0xAD:pass # PrimEnv: source texture mixes environment/primary.
                elif op in (0xFE,0xFF):return samples
                else:raise FormatError(f'Unsupported sleep particle command {op:#x}')
            else:raise FormatError('Sleep particle commands exceeded bounded steps')
        samples.append((size,pose,colors[0].copy(),colors[1].copy()))
    return samples


class SleepBubbles:
    def __init__(self,files,motion,matrices_at,time_offset=0):
        path=Path(files)/'EfCoData.dat';ar=Archive(path.read_bytes())
        table=ar.public('effCommonDataTable');bank=ar.pointer(table);tex_bank=ar.pointer(table+4)
        if ar.u16(bank)!=0x42 or ar.u32(bank+4)!=0 or ar.u32(bank+8)<=416:
            raise FormatError('Unsupported sleep particle bank layout')
        descriptor=bank+ar.u32(bank+12+416*4)
        kind,group,generator_life,life,flags,*values=struct.unpack('>4HI12f',ar.read(descriptor,60))
        if kind!=2 or generator_life!=1 or flags!=0x101 or values[7]!=-1:
            raise FormatError('Unsupported sleep bubble emitter')
        self.gravity,self.speed,self.radius,self.angle=values[0],values[3],abs(values[5]),abs(values[6])
        # values: gravity/friction/vx/vy/vz/radius/angle/random/size/params.
        self.samples=particle_samples(ar.read(descriptor+60,128),life,values[8])
        tg=tex_bank+ar.u32(tex_bank+4+group*4)
        count,fmt,palfmt,w,h=struct.unpack('>5I',ar.read(tg,20))
        if count!=1 or fmt!=3 or ar.u16(tg+20):raise FormatError('Unsupported sleep bubble texture')
        pixels=decode_image(ar.read(tex_bank+ar.u32(tg+24),image_size(w,h,fmt)),w,h,fmt)
        self.pixels=np.frombuffer(pixels,dtype='uint8').reshape(h,w,4)
        self.spawns=[];self.time_offset=time_offset
        rng=np.random.default_rng(416)
        for tick,spec in bubble_spawns(motion):
            if spec['common_joint'] or any(spec['range']):raise FormatError('Unsupported sleep bubble spawn attachment')
            matrix=matrices_at(tick)[spec['raw_joint']]
            origin=(matrix@np.array([*spec['offset'],1]))[:3]
            self.spawns.append((tick-time_offset,origin,float(rng.uniform(0,2*math.pi))))
        self.sha256=hashlib.sha256(path.read_bytes()).hexdigest()

    def active(self,tick,view):
        for spawn,origin,azimuth in self.spawns:
            age=tick-spawn
            if not 0<=age<len(self.samples):continue
            index=int(age);size,pose,primary,environment=self.samples[index]
            if index+1<len(self.samples):
                fraction=age-index;other=self.samples[index+1]
                size=size*(1-fraction)+other[0]*fraction
                primary=primary*(1-fraction)+other[2]*fraction;environment=environment*(1-fraction)+other[3]*fraction
            distance=self.speed*(age+1);radius=self.radius+distance*math.tan(self.angle)
            theta=azimuth+self.gravity*(age+1)
            center=origin+np.array([radius*math.cos(theta),distance,-radius*math.sin(theta)])
            corners=np.array([[-size,-size,0],[size,-size,0],[size,size,0],[-size,size,0]])@view.T+center
            yield corners,primary,environment

    def bounds(self,ticks,view):
        return [p for t in ticks for p,_,_ in self.active(t,view)]

    def render(self,tick,view,size,center,scale,background):
        image=background
        tex=self.pixels.astype(float)/255
        for corners,primary,environment in self.active(tick,view):
            pixels=np.empty_like(tex)
            pixels[:,:,:3]=(environment[:3]+(primary[:3]-environment[:3])*tex[:,:,:3])/255
            pixels[:,:,3]=(environment[3]+(primary[3]-environment[3])*tex[:,:,3])/255
            projected=(corners-center)@view
            projected[:,0]=size/2+projected[:,0]*scale;projected[:,1]=size/2-projected[:,1]*scale
            layer=rgba_triangles(size,projected,np.array([[0,1],[1,1],[1,0],[0,0]]),np.ones((4,4)),
                                 [[0,1,2],[0,2,3]],np.rint(np.clip(pixels,0,1)*255).astype('uint8'))
            image=Image.alpha_composite(image,layer)
        return image

    def provenance(self):
        return {'gfx_id':416,'source_archive':'EfCoData.dat','source_sha256':self.sha256,'particle_lifetime_ticks':len(self.samples),
                'spawn_ticks':[t for t,_,_ in self.spawns],'entrance_time_offset':self.time_offset,'random_seed':416,
                'limitations':['Focused original sprite/bytecode/trajectory; deterministic azimuth, approximate fractional sampling and foreground depth']}
