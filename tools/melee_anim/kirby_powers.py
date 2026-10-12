"""Kirby copy appearance: DOL costume tables, attached hats and reserved bones.

Source: ftkirbydata.c, ftKb_UnkMtxFunc0, ftKb_LoadHatParts and ftparts.c.
Assets/models stay local in ignored build/. Hat dynamics remain bind-pose based.
"""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct

import numpy as np

from .hsd import Archive, Dol, FormatError, load_symbols, read_global
from .catalog import CHARACTERS
from .roster import roster
from .inspect_models import visibility_lookup


def powers():
    return [{'slug':'none','label':'None / Kirby'}]+sorted(
        [{'slug':slug,'label':label} for slug,label in CHARACTERS if slug!='kirby'],key=lambda p:p['label'].casefold())


def validate_power(character, power):
    if power not in {p['slug'] for p in powers()}:
        raise ValueError('Unknown Kirby power')
    if power!='none' and character!='kirby':
        raise ValueError('Kirby Power is only available for Kirby')
    return power


def descriptor(repo, power, costume):
    validate_power('kirby',power)
    if power=='none':
        return None
    files=repo/'orig/GALE01/files'
    fighter=next(f for f in roster(files)['fighters'] if not f['paired_member'] and CHARACTERS[f['character_kind']][0]==power)
    kind=fighter['fighter_kind']
    dol=Dol((repo/'orig/GALE01/sys/main.dol').read_bytes());symbols=load_symbols(repo/'config/GALE01/symbols.txt')
    raw=read_global(dol,symbols,'ftKb_Init_803CA9D0')
    filename,symbol=struct.unpack_from('>II',raw,kind*8)
    if not filename or not symbol:
        raise FormatError('No copy appearance for this fighter')
    path=files/dol.cstring(filename);ar=Archive(path.read_bytes(),str(path));root=ar.public(dol.cstring(symbol))
    tables=read_global(dol,symbols,'ftKb_Init_803CB3E8');table=struct.unpack_from('>I',tables,kind*4)[0]
    result={'power':power,'fighter_kind':kind,'archive':path,'root':root,'mask':0,'body':None,'symbol':None}
    if table:
        filename,joint,_=struct.unpack('>III',dol.read(table+costume*12,12))
        result.update(body=files/dol.cstring(filename),symbol=dol.cstring(joint),mask=ar.u32(root+16))
        parts=root
    else:
        result['hat_root']=ar.pointer(root);parts=root+4
    count=ar.u32(parts);vis=ar.pointer(parts+4)
    if count>11 or vis is None:
        raise FormatError('Invalid Kirby copy parts descriptor')
    # Costume rows explicitly fall back to row zero, as ftParts_8007487C does.
    classes=[]
    for cls in range(4):
        row=ar.pointer(vis+costume*16+cls*4) if result['body'] else ar.pointer(vis+cls*4)
        if row is None:row=ar.pointer(vis+cls*4)
        classes.append({'groups':visibility_lookup(ar,row,count)})
    result['classes']=classes
    if power=='game-and-watch':
        result['outline_groups']=visibility_lookup(ar,ar.pointer(root+24),count)
    return result


def reserved_parts(repo):
    ar=Archive((repo/'orig/GALE01/files/PlCo.dat').read_bytes())
    table=ar.pointer(ar.public('ftLoadCommonData')+20);row=ar.pointer(table+4*4)
    at,count=ar.pointer(row),ar.u32(row+4)
    if count>32:raise FormatError('Too many Kirby reserved parts')
    return [list(ar.read(at+i*4,4)) for i in range(count)]


def bone_slots(count, parts, mask=0):
    unavailable={p[0] for i,p in enumerate(parts) if not mask & (1<<i)}
    result=[];slot=0
    while len(result)<count:
        if slot not in unavailable:result.append(slot)
        slot+=1
        if slot>140:raise FormatError('Kirby bone-slot mapping exceeds fighter limits')
    return result


def remap_tracks(tracks, source_count, target_count, parts, target_mask=0):
    # These are the source's distinct replacement rig sizes, not costume counts.
    source_masks={46:0,50:0xF,53:0x7F0,48:0x1800}
    if source_count not in source_masks:
        raise FormatError(f'Unsupported Kirby animation rig ({source_count} nodes)')
    source=bone_slots(source_count,parts,source_masks[source_count]);target=bone_slots(target_count,parts,target_mask)
    by_slot={slot:i for i,slot in enumerate(target)}
    return [replace(t,joint_index=by_slot[source[t.joint_index]]) for t in tracks if source[t.joint_index] in by_slot]


def model_for_power(repo, power, costume):
    from .export_model import export_fighter
    d=descriptor(repo,power,costume)
    folder=repo/'build/melee_anim/kirby-powers'/power/f'costume_{costume:02d}'
    sources=[d['archive'],repo/'orig/GALE01/sys/main.dol',repo/'orig/GALE01/files/PlCo.dat',repo/'config/GALE01/symbols.txt']
    if d['body']:sources.append(d['body'])
    sources.extend(Path(__file__).parent.glob('*.py'))
    digest=hashlib.sha256()
    for path in sorted(set(sources)):digest.update(path.read_bytes())
    key=digest.hexdigest();marker=folder/'inputs.json';target=folder/'model.json'
    valid=False
    if marker.is_file() and target.is_file():
        try:
            saved=json.loads(marker.read_text())
            valid=saved['key']==key and all((folder/n).is_file() and hashlib.sha256((folder/n).read_bytes()).hexdigest()==h for n,h in saved['files'].items())
            if valid:
                model=json.loads(target.read_text())
                valid=bool(model.get('materials')) and all(m.get('copy_diffuse_only') for m in model['materials'])
        except (ValueError,OSError,KeyError):pass
    if not valid:
        target,_=export_fighter(repo/'orig/GALE01/files',folder,4,costume,
            archive_path=d['body'] or d['archive'],root_symbol=d['symbol'],
            root_offset=None if d['body'] else d['hat_root'],copy_classes=d['classes'],reflection_preview=d['fighter_kind']==13,
            outline_groups=d.get('outline_groups'),color_mask_preview=d['fighter_kind']==14)
        model=json.loads(target.read_text())
        model.update(kirby_power=power,kirby_part_mask=d['mask'],kirby_appearance_mode='body' if d['body'] else 'hat')
        if power=='game-and-watch':
            ar=Archive(d['archive'].read_bytes());attrs=ar.pointer(d['root']+28)
            color=list(ar.read(attrs+4,4))
            for mat in model['materials']:mat.update(diffuse_rgba=color,alpha=1.0,unlit=True)
            model['runtime_root_scale']=[ar.f32(attrs),1,1]
            model['outline_rgba']=list(ar.read(attrs+8,4))
            from .export_model import configure_outline_materials
            configure_outline_materials(model,model['outline_rgba'])
        target.write_text(json.dumps(model,separators=(',',':'))+'\n')
        needed={'model.json'}|{t['image_file'] for m in model['materials'] for t in m['textures'] if t.get('image_file')}
        marker.write_text(json.dumps({'key':key,'files':{n:hashlib.sha256((folder/n).read_bytes()).hexdigest() for n in needed}}))
    return target,d


def attach_geometry(posed, head_matrix, root_bind):
    """The game copies part 6's world matrix to the hat root before drawing."""
    transform=head_matrix@np.linalg.inv(root_bind)
    normal_matrix=np.linalg.pinv(transform[:3,:3]).T
    result=[]
    for positions,normals in posed:
        p=positions@transform[:3,:3].T+transform[:3,3]
        n=normals@normal_matrix.T;n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12)
        result.append((p,n))
    return result
