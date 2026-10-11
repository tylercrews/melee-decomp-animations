"""Original common held-item meshes and joint curves for isolated attacks.

Reads Article/ItemModelDesc from ItCo, reusing the existing DAT/GX readers.
Attachment follows it_80274F48: position and orientation constraints, retaining
the item's scale. Projectiles, collisions and the general item script VM are
outside this focused playback path.
"""
import hashlib
import re
import struct
from pathlib import Path

import numpy as np

from .hsd import Archive, FormatError
from .inspect_models import inspect_model
from .export_model import decode_mesh, texture_matrix
from .ground_effects import aobj_tracks, matched_tree
from .texture import decode_image, image_size

SWINGS = ((108,12,'Beam Sword'),(112,11,'Home-Run Bat'),(116,13,'Parasol'),
          (120,24,'Fan'),(124,22,'Star Rod'),(128,23,"Lip's Stick"))


def item_for_motion(action, kind):
    """Use submotion IDs: packed clips often all have the name Swing1."""
    if kind in (27,28,32):
        return None
    match=re.fullmatch(r'attack-(\d+)',action)
    if not match:
        return None
    aid=int(match[1])
    if kind==2 and 295<=aid<=300:
        _,item,name=SWINGS[aid-295]
        return dict(item_kind=item,name=name,animation_id=0 if item in (12,13,23) else None,variant=4)
    for first,item,name in SWINGS:
        if first<=aid<first+4:
            variant=aid-first
            # Parasol starts closed; fighter commands select its swing curves.
            # Fan starts at bind pose until the source command variable fires.
            animation=0 if item in (12,13,23) else None
            return dict(item_kind=item,name=name,animation_id=animation,variant=variant)
    return None


def script_events(script, duration):
    """Bounded waits/calls/loops; collect only item-related commands."""
    blocks=[script]+script.get('reachable_blocks',[])
    commands={}
    for block in blocks:
        sequence=block.get('commands',[])
        for i,cmd in enumerate(sequence):commands[cmd['offset']]=(cmd,sequence[i+1]['offset'] if i+1<len(sequence) else None)
    sequence=script.get('commands',[])
    pc=sequence[0]['offset'] if sequence else None
    time=0;returns=[];loops=[];events=[]
    for _ in range(8192):
        if pc not in commands or time>duration:break
        cmd,next_pc=commands[pc];op=cmd['opcode'];word=int(cmd['first_word'],16)
        if op==0:break
        if op==1:time+=cmd['timer_ticks']
        elif op==2:time=max(time,cmd['timer_ticks'])
        elif op==3:loops.append([next_pc,word&0x3FFFFFF])
        elif op==4 and loops:
            loops[-1][1]-=1
            if loops[-1][1]>0:next_pc=loops[-1][0]
            else:loops.pop()
        elif op==5:
            returns.append(next_pc);next_pc=cmd.get('target')
        elif op==6:
            if not returns:break
            next_pc=returns.pop()
        elif op==7:next_pc=cmd.get('target')
        elif op in (19,42):events.append((time,cmd))
        pc=next_pc
    else:raise FormatError('Held-item script timing exceeds bounded commands')
    return events


def item_archive(files):
    """GALE01 US setting loads ItCo.usd (iteffect.c); retain DAT fallback."""
    files=Path(files)
    return files/('ItCo.usd' if (files/'ItCo.usd').is_file() else 'ItCo.dat')


def constrained_transform(target, anchor):
    """RObj position/rotation constraints preserve the item's column scales."""
    constrained=np.eye(4)
    constrained[:3,3]=target[:3,3]
    rotation=target[:3,:3]/np.maximum(np.linalg.norm(target[:3,:3],axis=0),1e-12)
    constrained[:3,:3]=rotation*np.linalg.norm(anchor[:3,:3],axis=0)
    return constrained@np.linalg.inv(anchor)


def billboard_matrix(matrix, view):
    """The Star Rod's leaf glow card uses JOBJ_BILLBOARD (camera facing)."""
    result=matrix.copy()
    result[:3,:3]=view*np.linalg.norm(matrix[:3,:3],axis=0)
    return result


def texture_color_generator(pixels, tev):
    """Supported item color generator: mix TEV0/KONST using texture RGB.

    Star Rod's I8 glow needs its yellow constants; displaying its grayscale
    intensity as RGB produces a dark disc. See MakeColorGenTExp in tobj.c.
    """
    result=pixels.copy()
    active=int.from_bytes(tev[28:32],'big')
    if active&0x40000000 and [tev[i] for i in (0,2,4,8,9,10,11)]==[0,0,0,133,128,8,15]:
        factor=pixels[:,:,:3]/255
        result[:,:,:3]=np.rint(np.asarray(list(tev[20:23]))*(1-factor)+np.asarray(list(tev[16:19]))*factor).astype('uint8')
    return result


def hold_joint(files, table, model, repo, specification=None):
    ar=Archive((Path(files)/table['fighter_archive']).read_bytes())
    parts=ar.pointer(ar.public(table['fighter_root'])+8)
    # ftpickupitem_800948A8 passes this raw part directly to ftLib_GetPartJObj.
    joint=ar.u8(parts+16)
    if specification and 'raw_joint' in specification:joint=specification['raw_joint']
    elif specification and 'canonical_part' in specification:
        from .character_props import mapped_joint
        joint=mapped_joint(files,model['fighter_kind'],specification['canonical_part'])
    if model['fighter_kind']==4:
        from .kirby_powers import bone_slots, reserved_parts
        slots=reserved_parts(repo)
        target=bone_slots(len(model['bones']),slots,model.get('kirby_part_mask',0))
        # fp->parts retains reserved holes even for ordinary Kirby. The DAT
        # mesh tree is compressed; runtime part slots are not mesh indices.
        joint={slot:i for i,slot in enumerate(target)}[joint]
    if joint>=len(model['bones']):
        raise FormatError('Held-item joint is outside the selected fighter rig')
    return joint


class HeldItem:
    def __init__(self, files, specification, duration, script=None):
        self.specification=specification
        self.duration=duration
        self.path=Path(files)/specification['source_archive'] if specification.get('source_archive') else item_archive(files)
        ar=Archive(self.path.read_bytes(),str(self.path))
        self.archive_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest()
        effect=specification.get('effect_table')
        if effect:
            effect_desc=ar.public(effect)+8+20*specification['effect_index']
            article=None;desc=None
            source=inspect_model(self.path,root_offset=ar.pointer(effect_desc+4))
        else:
            if specification.get('fighter_root'):
                common=ar.pointer(ar.public(specification['fighter_root'])+72)
                article=ar.pointer(common+4*specification['article_slot'])
            else:
                common=ar.pointer(ar.public('itPublicData')+4)
                article=ar.pointer(common+4*specification['item_kind'])
            desc=ar.pointer(article+16)
            source=inspect_model(self.path,root_offset=ar.pointer(desc))
        self.bones=source['joints']
        attach=0 if effect else ar.u32(desc+8)
        if not effect and not ar.u32(desc+4):
            # No dynamic bone table: runtime follows the child chain.
            index=0
            for _ in range(attach):
                children=[b['index'] for b in self.bones if b['parent']==index]
                if not children:raise FormatError('Item attachment child is missing')
                index=children[0]
            attach=index
        if attach>=len(self.bones):raise FormatError('Item attachment exceeds rig')
        self.attach_joint=attach
        if specification['item_kind']==12:
            # itsword.c: settled PickedUp has x28=2, x10=1 and x40=attrs.x10.
            # These override blade/glow SRT after joint animation each tick.
            attrs=ar.pointer(article+4)
            self.sword_held_scale=.6*self.bones[6]['scale'][1]
            self.sword_glow=ar.f32(attrs+16)
        # PickedUp clears HIDDEN throughout the item's child subtree.
        for b in self.bones[1:]:b['flags']&=~0x10
        self.animations={}
        self.timeline=[(0,specification['animation_id'],1.)]
        self.visibility_events=[(0,True)]
        behavior=specification.get('behavior')
        if behavior=='blaster':
            # Neutral end begins visible and the source cmd_var1=2 hides it.
            for time,cmd in script_events(script or {},duration):
                var=cmd.get('command_variable')
                if var and var['index']==1:self.visibility_events.append((time,var['value']!=2))
        elif behavior=='hammer':
            self.visibility_events=[(0,False)]
            for time,cmd in script_events(script or {},duration):
                var=cmd.get('command_variable')
                if var and var['index']==0 and var['value'] in (1,2):self.visibility_events.append((time,var['value']==1))
        elif behavior=='cape':
            self.visibility_events=[(0,True)]
            for time,cmd in script_events(script or {},duration):
                var=cmd.get('command_variable')
                if var and var['index']==1:self.visibility_events.append((time,var['value']!=0))
        for time,cmd in script_events(script or {},duration):
            word=int(cmd['first_word'],16)
            if specification['item_kind']==13 and cmd['opcode']==42:
                mode=(word>>13)&8191;div=word&8191
                if mode>6:raise FormatError('Unknown Parasol animation command')
                animation=(4,5,6,7,2,3,1)[mode]
                speed=(20,16,45,2,20,30,40,16)[animation]/div if div else 1.
                self.timeline.append((time,animation,speed))
            elif specification['item_kind']==24 and cmd['opcode']==19:
                var=cmd['command_variable']
                if var['index']==0 and var['value'] in (1,2):
                    animation=(0,1,2,1,2)[specification['variant']] if var['value']==1 else 3
                    self.timeline.append((time,animation,1.))
        states=None if effect else ar.pointer(article+12)
        for animation in {a for _,a,_ in self.timeline if a is not None}:
            tracks=[];timing={}
            def visit(index,node):
                aobj=ar.pointer(node+8)
                ts=aobj_tracks(ar,aobj,index)
                tracks.extend(ts)
                if aobj is not None:timing[index]=(ar.f32(aobj+4),bool(ar.u32(aobj)&0x20000000))
            matched_tree(ar,self.bones,ar.pointer(effect_desc+8) if effect else ar.pointer(states+animation*16),visit)
            self.animations[animation]=(tracks,timing)
        ids={m['offset']:i for i,m in enumerate(source['materials'])}
        materials=source['materials']
        self.textures={}
        for material in materials:
            material['diffuse_texture_only']=True
            material['unlit']=bool(material['render_mode']&1)
            material['item_alpha_blend']=bool(material['render_mode']&0x40000000)
            for t in material['textures']:
                at=t['offset'];image=ar.pointer(at+76);pal=ar.pointer(at+80)
                t.update(coordinate_type=t['flags']&15,
                         rotation=list(struct.unpack('>3f',ar.read(at+16,12))),
                         scale=list(struct.unpack('>3f',ar.read(at+28,12))),
                         translation=list(struct.unpack('>3f',ar.read(at+40,12))),
                         repeat_s=ar.u8(at+60),repeat_t=ar.u8(at+61),
                         wrap_s=ar.u32(at+52),wrap_t=ar.u32(at+56))
                t['texture_matrix']=texture_matrix(t).tolist()
                if image is not None:
                    w,h,fmt=ar.u16(image+4),ar.u16(image+6),ar.u32(image+8)
                    palette=ar.read(ar.pointer(pal),ar.u16(pal+12)*2) if pal is not None else None
                    pixels=decode_image(ar.read(ar.pointer(image),image_size(w,h,fmt)),w,h,fmt,palette,ar.u32(pal+4) if pal is not None else 1)
                    name=f'item/{specification["item_kind"]}/{at}'
                    t['image_file']=name
                    pixels=np.frombuffer(pixels,dtype='uint8').reshape(h,w,4)
                    if t['tev'] is not None:pixels=texture_color_generator(pixels,ar.read(t['tev'],32))
                    self.textures[name]=pixels
        meshes=[]
        for polygon in source['polygons']:
            mesh=decode_mesh(ar,polygon)
            mesh.update(owner_joint_index=polygon['joint_index'],drawable_index=polygon['drawable_index'],
                        material_index=ids[source['drawables'][polygon['drawable_index']]['material']],
                        cull_flags=polygon['flags'],envelopes=polygon.get('envelopes') or
                        [[dict(joint_index=polygon['joint_index'],weight=1.)]]+
                        ([[dict(joint_index=polygon['shared_joint_index'],weight=1.)]] if polygon.get('shared_joint_index') is not None else []))
            meshes.append(mesh)
        self.model=dict(bones=self.bones,materials=materials,meshes=meshes)
        if specification.get('behavior')=='needle-release':
            self.model['meshes']=[dict(m) for _ in specification['shot_ticks'] for m in meshes]
        self.anchor_at=None

    def pose(self, target, frame, view=None):
        from .preview import deform, joint_visibility, pose_matrices
        if self.specification.get('behavior')=='needle-release':
            from .export_model import local_matrix
            spec=self.specification;geometry=[];shown=[];shots=spec['shot_ticks']
            meshes_per_shot=len(self.model['meshes'])//len(shots)
            angle=np.pi/4 if 'Air' in spec['phase'] else 0.
            # it_802AFF08 emits along game +X for the right-facing preset.
            # Item root facing rotates its model's local Z into that axis.
            velocity=spec['projectile_speed']*np.array([np.cos(angle),-np.sin(angle),0.])
            source=pose_matrices(self.bones,[],0,tree_type=None)
            for i,tick in enumerate(shots):
                origin=self.anchor_at(tick) if self.anchor_at else target
                elapsed=max(0,frame-tick)
                position=origin[:3,3]+[spec['spawn_offset'][0],spec['spawn_offset'][1],0]+velocity*elapsed
                transform=local_matrix([angle,np.pi/2,0],[1,1,1],position)
                matrices=np.asarray([transform@m for m in source])
                active=tick<=frame<tick+spec['projectile_lifetime']
                for mesh in self.model['meshes'][i*meshes_per_shot:(i+1)*meshes_per_shot]:
                    geometry.append(deform(mesh,matrices,self.bones));shown.append(active)
            return geometry,shown
        # Each HSD_AObj has its own end/loop; hold nonlooping terminal curves.
        evaluated=[]
        start,animation,speed=next(event for event in reversed(self.timeline) if event[0]<=frame)
        tracks,timing=self.animations.get(animation,([],{}))
        elapsed=(frame-start)*speed+self.specification.get('phase_offset',0)
        for track in tracks:
            end,loop=timing[track.joint_index]
            time=elapsed%end if loop and end>0 else min(elapsed,end) if end>0 else elapsed
            value=track.evaluate(time)
            if value is not None:
                from .motions import Track
                # A constant sampled FObj preserves pose_matrices semantics.
                evaluated.append(Track(track.joint_index,track.channel,0,0,0,b'\x11'+struct.pack('<f',value)+b'\x01'+struct.pack('<f',value)))
        matrices=pose_matrices(self.bones,evaluated,0,tree_type=None)
        if self.specification['item_kind']==12:
            from .motions import Track
            overrides={6:{9:self.sword_held_scale},3:{8:1.5*self.sword_glow+self.sword_held_scale,
                                                       9:self.sword_glow+self.sword_held_scale,
                                                       10:1.5*self.sword_glow+self.sword_held_scale}}
            for joint,values in overrides.items():
                evaluated=[t for t in evaluated if not (t.joint_index==joint and t.channel in values)]
                evaluated.extend(Track(joint,ch,0,0,0,b'\x11'+struct.pack('<f',v)+b'\x01'+struct.pack('<f',v)) for ch,v in values.items())
            matrices=pose_matrices(self.bones,evaluated,0,tree_type=None)
        transform=constrained_transform(target,matrices[self.attach_joint])
        scale=self.specification.get('scale',1.)
        transform[:3,:3]*=scale
        transform[:3,3]=target[:3,3]-transform[:3,:3]@matrices[self.attach_joint][:3,3]
        constrained=np.asarray([transform@m for m in matrices])
        if view is not None:
            for b in self.bones:
                if b['flags']&0xe00==0x200:
                    constrained[b['index']]=billboard_matrix(constrained[b['index']],view)
        geometry=[deform(mesh,constrained,self.bones) for mesh in self.model['meshes']]
        shown=joint_visibility(self.bones,evaluated,0)
        if not next(v for time,v in reversed(self.visibility_events) if time<=frame):shown=[False]*len(shown)
        return geometry,[shown[m['owner_joint_index']] for m in self.model['meshes']]

    def provenance(self):
        return {**self.specification,'source_archive':self.path.name,'archive_sha256':self.archive_sha256,
                'item_attach_joint':self.attach_joint,'joint_animation':any(t for t,_ in self.animations.values()),
                'animation_timeline':self.timeline,
                'visibility_timeline':self.visibility_events,
                'limitations':['No collisions or general item script/material VM',
                               'Six deterministic free-flight needles; no bounce/hit effects' if self.specification.get('behavior')=='needle-release' else 'Emitted projectiles are not played for this attached prop',
                               'Character-specific dynamic/material callbacks and full GX glow remain approximate']}
