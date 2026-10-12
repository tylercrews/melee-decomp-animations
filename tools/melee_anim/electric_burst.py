"""Focused original electric-hit generator12/children13..18, deterministic preset."""
import math,struct
from pathlib import Path
import numpy as np
from PIL import Image
from .hsd import Archive,FormatError
from .texture import decode_image,image_size
from .ground_effects import rgba_triangles


def is_judge9(character,action):
    return character=='game-and-watch' and action in ('attack-305_source','attack-314_source')


def particle_program(program,life,size,velocity,rng):
    pc=0;wait=0;loop=None;position=np.zeros(3);velocity=np.array(velocity,dtype=float)
    colors=[np.full(4,255.),np.zeros(4)];targets=[c.copy() for c in colors];remain=[0,0]
    target=size;size_remain=0;rotation=rot_target=0.;rot_remain=0;pose=0;samples=[]
    def byte():
        nonlocal pc
        value=program[pc];pc+=1;return value
    def count():
        value=byte();return ((value&127)<<8)+byte() if value&128 else value
    def floating():
        nonlocal pc
        value=struct.unpack_from('>f',program,pc)[0];pc+=4
        if not math.isfinite(value):raise FormatError('Nonfinite electric particle value')
        return value
    for age in range(life):
        if size_remain:size+=(target-size)/size_remain;size_remain-=1
        if rot_remain:rotation+=(rot_target-rotation)/rot_remain;rot_remain-=1
        for i in range(2):
            if remain[i]:colors[i]+=(targets[i]-colors[i])/remain[i];remain[i]-=1
        if wait:wait-=1
        if not wait:
            for _ in range(256):
                op=byte()
                if op<128:
                    wait=op&31
                    if op&32:wait=(wait<<8)+byte()
                    if op&64:pose=byte()
                    if wait:break
                elif op in (0xA0,0xAC):
                    size_remain=count();target=floating()+(floating()*rng.random() if op==0xAC else 0)
                    if not size_remain:size=target
                elif op&0xF0 in (0xC0,0xD0):
                    i=0 if op&0xF0==0xC0 else 1;remain[i]=count();targets[i]=colors[i].copy()
                    for channel in range(4):
                        if op&(1<<channel):targets[i][channel]=byte()
                    if not remain[i]:colors[i]=targets[i].copy()
                elif op==0xED:
                    base,span,steps=floating(),floating(),byte();random=rng.random()
                    value=base+span*(int(random*(steps+1))/steps if steps else random)
                    rotation+=value;rot_target+=value
                elif op==0xB6:
                    rot_remain=count();rot_target+=floating()
                    if not rot_remain:rotation=rot_target
                elif op==0xBC:
                    first,span=byte(),byte();pose=int(first+span*rng.random())
                elif op==0xBD:
                    speed=floating()+floating()*rng.random();norm=np.linalg.norm(velocity)
                    if norm>1e-10:velocity*=speed/norm
                elif op in (0xAD,0xAE):
                    pass # PrimEnv / clear mirror flags; no operands
                elif op==0xFA:loop=[byte(),pc]
                elif op==0xFB:
                    loop[0]-=1
                    if loop[0]:pc=loop[1]
                elif 0x80<=op<=0x9F:
                    cls=op&0xF8
                    for axis in range(3):
                        if op&(1<<axis):
                            value=floating();array=position if cls<0x90 else velocity
                            array[axis]=array[axis]+value if cls in (0x88,0x98) else value
                elif op in (0xFE,0xFF):return samples
                else:raise FormatError(f'Unsupported electric particle command {op:#x}')
            else:raise FormatError('Electric particle command limit exceeded')
        samples.append((size,pose,colors[0].copy(),colors[1].copy(),rotation,position.copy()))
        position+=velocity
    return samples


class ElectricBurst:
    def __init__(self,files,origin,tick=16):
        self.origin=origin;self.tick=tick;self.entries=[];self.textures={}
        ar=Archive((Path(files)/'EfCoData.dat').read_bytes());table=ar.public('effCommonDataTable')
        bank,tex_bank=ar.pointer(table),ar.pointer(table+4);n=ar.u32(bank+8)
        offsets=[ar.u32(bank+12+i*4) for i in range(n)];rng=np.random.default_rng(12)
        for emitter in range(13,19):
            at=bank+offsets[emitter];kind,group,span,life,flags,*v=struct.unpack('>4HI12f',ar.read(at,60))
            length=min(o for o in offsets if o>offsets[emitter])-offsets[emitter]-60
            program=ar.read(at+60,length)
            tg=tex_bank+ar.u32(tex_bank+4+group*4);count,fmt,palfmt,w,h=struct.unpack('>5I',ar.read(tg,20))
            if ar.u16(tg+20):raise FormatError('Paletted electric sprite is unsupported')
            images=[]
            for i in range(count):
                data=ar.read(tex_bank+ar.u32(tg+24+i*4),image_size(w,h,fmt))
                pixels=np.frombuffer(decode_image(data,w,h,fmt),dtype='uint8').reshape(h,w,4).copy()
                # GX intensity sprites feed intensity into the particle alpha
                # combiner; the ordinary material decoder keeps opaque alpha.
                if fmt in (0,1):pixels[:,:,3]=pixels[:,:,0]
                images.append(pixels)
            self.textures[group]=images
            for emit in range(span):
                for _ in range(max(1,math.ceil(abs(v[7])))):
                    angle=rng.uniform(0,2*math.pi);direction=np.array([math.cos(angle),math.sin(angle),0.])
                    velocity=direction*abs(v[3])+[0,0,v[4]]
                    samples=particle_program(program,life,v[8],velocity,rng)
                    offset=direction*abs(v[5])*rng.random()
                    self.entries.append((emit,group,samples,offset,v[1]))

    def active(self,tick,view):
        for start,group,samples,offset,friction in self.entries:
            age=tick-self.tick-start
            if not 0<=age<len(samples):continue
            size,pose,primary,environment,rotation,displacement=samples[int(age)]
            if not size:continue
            # Keep source curve values; trajectories are a deterministic planar
            # contact preset rather than an opponent/collision simulation.
            center=self.origin+offset+displacement*(friction**age if friction else 1)
            corners=np.array([[-size,-size],[size,-size],[size,size],[-size,size]])
            c,s=math.cos(rotation),math.sin(rotation);corners=corners@np.array([[c,s],[-s,c]])
            corners=np.column_stack((corners,np.zeros(4)))@view.T+center
            pixels=self.textures[group][pose];t=pixels.astype(float)/255
            rgba=np.empty_like(t);rgba[:,:,:3]=(environment[:3]+(primary[:3]-environment[:3])*t[:,:,:3])/255
            rgba[:,:,3]=(environment[3]+(primary[3]-environment[3])*t[:,:,3])/255
            # Portable transparent exports represent this light burst with
            # emissive coverage: zero-radiance phases add no dark sprite card.
            # Preserve premultiplied radiance while encoding standard RGBA.
            radiance=rgba[:,:,:3].max(axis=2)
            rgba[:,:,3]*=radiance
            rgba[:,:,:3]/=np.maximum(radiance[:,:,None],1e-8)
            yield corners,np.rint(np.clip(rgba,0,1)*255).astype('uint8')

    def bounds(self,ticks,view):return [p for t in ticks for p,_ in self.active(t,view)]

    def render(self,tick,view,size,center,scale,image):
        for corners,pixels in self.active(tick,view):
            p=(corners-center)@view;p[:,0]=size/2+p[:,0]*scale;p[:,1]=size/2-p[:,1]*scale
            layer=rgba_triangles(size,p,np.array([[0,1],[1,1],[1,0],[0,0]]),np.ones((4,4)),[[0,1,2],[0,2,3]],pixels)
            image=Image.alpha_composite(image,layer)
        return image
