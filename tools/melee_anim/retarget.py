"""Play other fighters' results/taunt poses on the wireframe skeletons.

User-requested presentation: the original game never shows these clips on a
wireframe. Joint correspondence reuses the game's own cross-fighter animation
path (ftAnim_8006FCE4): every source joint goes through ftPartsRemap, i.e.
PlCo ftLoadCommonData+0x10 FighterPartsTable joint_to_part -> part_to_joint.
Joints that table leaves unmapped (Ganondorf has no head part) are matched by
bind position, parent before child, inside the same mapped subtree. Mapped
joints copy the source joint's world rotation: the inspected rigs share local
bone axes, so this is the game's local-rotation copy without the error that
unmapped intermediate joints would add. Only the root parts that
ftParts_80074E58 marks for full SRT take translation, scaled by hip height;
fn_8001E60C likewise drops translation for ordinary joints. Scale channels are
not transferred. Identical skeletons (Male Wireframe and Captain Falcon) play
the original tracks unchanged.
"""
from dataclasses import dataclass
import json
import math
from pathlib import Path

import numpy as np

from .export_model import local_matrix
from .hsd import Archive, FormatError
from .motions import read_figatree
from .inspect_motions import read_exact_motion

POSES = (('victory1','source','Victory 1'),('victory1','wait','Victory 1 loop'),
         ('victory2','source','Victory 2'),('victory2','wait','Victory 2 loop'),
         ('victory3','source','Victory 3'),('victory3','wait','Victory 3 loop'),
         ('taunt','source','Taunt'))
WIREFRAME_SOURCES = {'male-wireframe':('captain-falcon','ganondorf','marth'),
                     'female-wireframe':('sheik','samus','peach')}
WIREFRAME_CLAPS = {'male-wireframe':'captain-falcon','female-wireframe':'sheik'}
CLAP = ('results-clap','source','Clapping')
ROOT_PARTS = (0,1,2,3,4,52)  # TopN, TransN, XRotN, YRotN, HipN, TransN2
HIP_PART = 4
# LFootJA, LFootJ, RFootJA, RFootJ: rest angle is footwear (Sheik/Samus heels),
# not pose, so these and their toes transfer rotation relative to bind.
FOOT_PARTS = (9,10,14,15)
MATCH_TOLERANCE = .15  # fraction of target hip height for bind-position matches


def model_path(repo, slug):
    return Path(repo)/'build/melee_anim/exported'/slug/'costume_00/model.json'


class PartsTable:
    """FighterPartsTable rows from PlCo.dat for any fighter kind."""
    def __init__(self, files):
        self.ar=Archive((Path(files)/'PlCo.dat').read_bytes())
        self.table=self.ar.pointer(self.ar.public('ftLoadCommonData')+16)

    def joint(self, kind, part):
        joint=self.ar.u8(self.ar.pointer(self.ar.pointer(self.table+kind*4)+4)+part)
        return None if joint==255 else joint

    def remap(self, source_kind, target_kind, target_count):
        """ftPartsRemap for each source joint; returns target joint -> source joint."""
        row=self.ar.pointer(self.table+source_kind*4)
        result={}
        for joint in range(self.ar.u32(row+8)):
            part=self.ar.u8(self.ar.pointer(row)+joint)
            mapped=None if part==255 else self.joint(target_kind,part)
            if mapped is None:continue
            if mapped>=target_count:raise FormatError('Parts table exceeds the target skeleton')
            result.setdefault(mapped,joint)
        return result

    def hip_height(self, model):
        height=np.asarray(model['bones'][self.joint(model['fighter_kind'],HIP_PART)]['world_bind_matrix'])[1,3]
        if height<=0:raise FormatError('Hip joint is not above the ground plane')
        return height


def rotation(matrix):
    """Nearest proper rotation; removes any joint scale."""
    u,_,vt=np.linalg.svd(np.asarray(matrix,dtype=float)[:3,:3])
    return u@np.diag([1,1,np.sign(np.linalg.det(u@vt))])@vt


def euler(matrix):
    """Inverse of HSD_MtxSRT's Rz*Ry*Rx."""
    y=math.asin(max(-1.,min(1.,-matrix[2,0])))
    if math.cos(y)>1e-6:
        return [math.atan2(matrix[2,1],matrix[2,2]),y,math.atan2(matrix[1,0],matrix[0,0])]
    return [math.atan2(-matrix[1,2],matrix[1,1]),y,0.]


def identical_skeleton(source, target):
    return len(source['bones'])==len(target['bones']) and all(
        a['parent']==b['parent'] and all(np.allclose(a[k],b[k],atol=1e-4) for k in ('rotation','scale','position'))
        for a,b in zip(source['bones'],target['bones']))


def anchors(bones, mapped):
    """Nearest mapped strict ancestor of every joint (parent-before-child order)."""
    result=[]
    for bone in bones:
        parent=bone['parent']
        result.append(None if parent is None else parent if parent in mapped else result[parent])
    return result


def bind_positions(model):
    return np.array([np.asarray(b['world_bind_matrix'])[:3,3] for b in model['bones']])


def correspondence(parts, source, target):
    """Game part remap, then bind-position matches for the remaining joints.

    A target joint is only considered once its parent is settled, so a chain
    is matched from its base (the closest overall pair is taken first). Its
    candidates are free source joints directly below the counterpart of its
    nearest matched ancestor, compared as hip-scaled offsets from that pair.
    """
    mapping=parts.remap(source['fighter_kind'],target['fighter_kind'],len(target['bones']))
    ps,pt=bind_positions(source),bind_positions(target)
    ratio=parts.hip_height(target)/parts.hip_height(source)
    limit=MATCH_TOLERANCE*parts.hip_height(target)
    filled={};settled=set(mapping)
    while True:
        matched={**mapping,**filled}
        target_anchor=anchors(target['bones'],set(matched))
        source_anchor=np.array([-1 if a is None else a for a in anchors(source['bones'],set(matched.values()))])
        free=np.ones(len(ps),bool);free[list(matched.values())]=False
        frontier=[j for j,b in enumerate(target['bones']) if j not in settled and b['parent'] in settled]
        if not frontier:return matched,filled
        best=None
        for joint in frontier:
            anchor=target_anchor[joint]
            pool=np.flatnonzero(free&(source_anchor==matched[anchor])) if anchor is not None else []
            if not len(pool):
                settled.add(joint);continue
            distance=np.linalg.norm(pt[joint]-pt[anchor]-(ps[pool]-ps[matched[anchor]])*ratio,axis=1)
            i=int(np.argmin(distance))
            if distance[i]>limit:settled.add(joint)
            elif best is None or distance[i]<best[0]:best=(distance[i],joint,int(pool[i]))
        if best:
            filled[best[1]]=best[2];settled.add(best[1])


@dataclass(frozen=True, eq=False)
class RetargetedTrack:
    """Track-like channel evaluated from the solved target pose."""
    joint_index: int
    channel: int
    solver: 'PoseRetarget'

    def evaluate(self, frame):
        rotation_value,position=self.solver.solve(frame)[self.joint_index]
        return rotation_value[self.channel-1] if self.channel<5 else position[self.channel-5]


class PoseRetarget:
    def __init__(self, parts, source, target, tracks, tree_type):
        self.source,self.target,self.source_tracks,self.tree_type=source,target,tracks,tree_type
        self.mapping,self.filled=correspondence(parts,source,target)
        self.ratio=parts.hip_height(target)/parts.hip_height(source)
        self.roots={parts.joint(target['fighter_kind'],p) for p in ROOT_PARTS}&set(self.mapping)
        feet={parts.joint(target['fighter_kind'],p) for p in FOOT_PARTS}-{None}
        for bone in target['bones']:
            if bone['parent'] in feet:feet.add(bone['index'])
        self.rest={j:rotation(source['bones'][self.mapping[j]]['world_bind_matrix']).T@rotation(target['bones'][j]['world_bind_matrix'])
                   for j in feet&set(self.mapping)}
        self.bind_rotations=[local_matrix(b['rotation'],[1,1,1],[0,0,0])[:3,:3] for b in target['bones']]
        self.cache=(None,None)

    def tracks(self):
        return [RetargetedTrack(j,c,self) for j in sorted(self.mapping) for c in ((1,2,3,5,6,7) if j in self.roots else (1,2,3))]

    def solve(self, frame):
        if self.cache[0]==frame:return self.cache[1]
        from .preview import pose_matrices
        world=pose_matrices(self.source['bones'],self.source_tracks,frame,self.tree_type)
        rotations=[];result={}
        for bone in self.target['bones']:
            joint,parent=bone['index'],bone['parent']
            if joint!=len(rotations):raise FormatError('Target joints are not parent-before-child')
            above=rotations[parent] if parent is not None else np.eye(3)
            if joint not in self.mapping:
                rotations.append(above@self.bind_rotations[joint]);continue
            other=self.mapping[joint]
            desired=rotation(world[other])
            if joint in self.rest:desired=desired@self.rest[joint]
            position=list(bone['position'])
            if joint in self.roots:
                up=self.source['bones'][other]['parent']
                local=world[other] if up is None else np.linalg.inv(world[up])@world[other]
                position=list(np.asarray(bone['position'])+(local[:3,3]-np.asarray(self.source['bones'][other]['position']))*self.ratio)
            result[joint]=(euler(above.T@desired),position)
            rotations.append(desired)
        self.cache=(frame,result)
        return result

    def provenance(self):
        return {'method':'semantic parts','game_part_matches':len(self.mapping)-len(self.filled),
                'bind_position_matches':{str(k):v for k,v in sorted(self.filled.items())},
                'root_translation_scale':self.ratio}


def retarget_tracks(files, retarget, target, tracks, tree_type, repo):
    """Target-rig tracks plus provenance for a cataloged borrowed pose."""
    source=json.loads((Path(repo)/retarget['model']).read_text())
    if identical_skeleton(source,target):
        return tracks,{'method':'identical skeleton; original tracks unchanged'}
    solver=PoseRetarget(PartsTable(files),source,target,tracks,tree_type)
    return solver.tracks(),solver.provenance()


def retarget_inputs(repo, actor):
    """Extra cache-fingerprint inputs for a borrowed pose."""
    if not actor.get('retarget'):return []
    return [Path(repo)/actor['retarget']['model'],Path(repo)/'orig/GALE01/files/PlCo.dat',Path(__file__)]


def borrowed_clap_cycles(root, retarget, times):
    """The source fighter's validated clap intervals and 42-frame sync plan.

    A borrowed clap samples the same source clip at the same source times, so
    the source character's minimum/dirty frame interval and fractional sync
    schedule apply unchanged. Each is accepted only while its fingerprint still
    matches the source character's clapping masters, as for the original clip.
    """
    if retarget['action']!='results-clap':return {}
    from .catalog import CHARACTERS
    from .cycles import input_fingerprint, read_cycles
    root=Path(root);slug=retarget['character']
    manifests=sorted((root/slug).glob('costume_*/results-clap_source/preview-manifest.json'))
    if not manifests:return {}
    source_times=json.loads(manifests[0].read_text())['sample_source_times']
    if len(source_times)!=len(times) or not np.allclose(source_times,times,atol=1e-9,rtol=0):
        return {}
    fingerprint=input_fingerprint(manifests);label=dict(CHARACTERS)[slug];result={}
    for report_key,clip_key in (('characters','minimum_cycle'),('dirty_characters','dirty_cycle')):
        cycle=read_cycles(root,report_key).get(slug)
        if cycle and cycle.get('input_fingerprint')==fingerprint and cycle['full_length']==len(times):
            result[clip_key]={**{k:v for k,v in cycle.items() if k!='input_fingerprint'},'timing_from':label}
    path=root/'clapping-sync.json'
    plan=json.loads(path.read_text())['characters'].get(slug) if path.is_file() else None
    if plan and plan['input_fingerprint']==fingerprint:
        plan={k:v for k,v in plan.items() if k!='input_fingerprint'}
        result['sync_cycle']={**{k:v for k,v in plan.items() if k!='fit_source_times'},'plan':plan,'timing_from':label}
    return result


def clip_tracks(files, actor):
    blob=(Path(files)/actor['animation_file']).read_bytes()
    return read_figatree(read_exact_motion(blob,actor['clip'],actor['animation_file']),actor['clip']['symbol'])[1]


def wireframe_actions(repo, report, slug, kind, own_actions):
    """Requested victory/taunt/clapping entries for a wireframe; relabels own taunts.

    The wireframes' own taunts are byte-identical to an original fighter's
    (Male: Captain Falcon, Female: Zelda), so a requested copy is not added
    twice; the own entries are named after that fighter instead.
    """
    from .catalog import CHARACTERS
    from .preview import load_clip
    from .roster import roster
    repo=Path(repo);files=repo/'orig/GALE01/files'
    fighters={CHARACTERS[f['character_kind']][0]:f['fighter_kind'] for f in roster(files)['fighters']
              if not f['paired_member'] and f['character_kind']<len(CHARACTERS)}
    names=dict(CHARACTERS)
    taunts={}
    for character,source_kind in fighters.items():
        motion,_,tracks=load_clip(report,'taunt','source',files,source_kind)
        taunts[motion['symbol'].split('_Share_')[0]]=(character,motion['symbol'],tracks)
    owned=set()
    for action in own_actions:
        if action.get('animation_type')!='taunt' or not action['available']:continue
        actor=action['actors'][0];symbol=actor['clip']['symbol']
        author=taunts.get(symbol.split('_Share_')[0])
        if author is None:continue
        character,standard,tracks=author
        if symbol==standard:
            if clip_tracks(files,actor)!=tracks:continue
            owned.add(character);action['label']=f'{names[character]} — Taunt'
        elif symbol.removesuffix('_figatree').endswith('AppealL'):
            action['label']=f'{names[character]} — Taunt (facing left)'
    target=json.loads(model_path(repo,slug).read_text())
    actions=[]
    for character in WIREFRAME_SOURCES.get(slug,()):
        source_kind=fighters[character]
        relative=model_path(repo,character).relative_to(repo).as_posix()
        method='identical skeleton' if identical_skeleton(json.loads((repo/relative).read_text()),target) else 'semantic parts'
        for action,section,title in POSES+((CLAP,) if WIREFRAME_CLAPS.get(slug)==character else ()):
            if action=='taunt' and character in owned:continue
            motion,metadata,_=load_clip(report,action,section,files,source_kind)
            if action=='taunt':
                table=next(t for t in report['taunts'] if t['fighter_kind']==source_kind)
                chosen=table['standard_facing']['right']['source_fighter_kind']
                archive=next(t for t in report['taunts'] if t['fighter_kind']==chosen)['animation_file']
            else:
                archive=next(t for t in report['results'] if t['fighter_kind']==source_kind)['results_archive']
            category={'taunt':'taunt','results-clap':'clapping'}.get(action,'victory')
            key=f'other-{character}-{action}'+('-loop' if section=='wait' else '')
            clip={'symbol':motion['symbol'],'frames':metadata['frames'],'type':metadata['type'],
                  'node_count':len(target['bones']),'source_node_count':metadata['node_count'],
                  'motion_loop':motion.get('motion_loop',False),
                  'effective_loop':motion.get('effective_loop',motion.get('motion_loop',False)),'script':{}}
            actions.append({'key':key+'_source','animation_id':None,'animation_type':category,'ground_effect':None,
                            'name':f'{names[character]} {title}','label':f'{names[character]} — {title}',
                            'group':{'victory':'Victory poses','taunt':'Taunts','clapping':'Clapping'}[category],
                            'actors':[{'fighter_kind':kind,'source_fighter_kind':source_kind,'visibility_override':None,
                                       'character_prop':None,'character_effects':[],'animation_file':archive,'clip':clip,
                                       'retarget':{'character':character,'fighter_kind':source_kind,'action':action,
                                                   'section':section,'model':relative,'method':method}}],
                            'held_item':None,'character_effects':[],'available':True,'unavailable_reason':None})
    return actions


def main():
    """Pre-render every borrowed wireframe clip into the ordinary on-demand caches.

    Normal results/taunt/clap masters are prebuilt during import; borrowed
    poses are lazy catalog clips, so render them (and each borrowed clap's
    synced view) once here. Cache keys include tools/melee_anim/*.py, so rerun
    this after code changes to avoid slow first views in the player.
    """
    import argparse, time
    from .attacks import AttackCache, CATALOG, virtual_clips
    from .rotations import RotationCache
    parser=argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('--root',type=Path,default=Path('build/melee_anim/preview'))
    args=parser.parse_args()
    catalog=json.loads((args.root/CATALOG).read_text())
    keys={(f['character'],a['key']) for f in catalog['characters'] for a in f['actions']
          if a['available'] and a['actors'][0].get('retarget')}
    clips=[c for c in virtual_clips(args.root) if (c['character'],c['action_key']) in keys]
    attacks,rotations=AttackCache(args.root),RotationCache(args.root)
    for i,clip in enumerate(clips,1):
        started=time.monotonic()
        prepared=attacks.get(clip)
        if clip.get('sync_cycle'):rotations.get(prepared,(0,0,0),sync=True)
        print(f'Borrowed poses {i}/{len(clips)}: {clip["character_label"]} — {clip["action_label"]} '
              f'({time.monotonic()-started:.1f}s)',flush=True)


if __name__=='__main__':
    main()
