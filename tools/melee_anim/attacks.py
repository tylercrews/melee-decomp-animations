"""Catalog original attack/ground-recovery clips; render costumes on demand.

Animation IDs come from ftData.xC, never the demo table or motion-state IDs.
Generated catalogs, PNG/GIF masters and content-addressed caches stay in build/.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

from .catalog import ALL_CHARACTERS
from .render_settings import native_size
from .hsd import Archive, Dol, load_symbols, read_global
from .inspect_motions import motion_entries, read_exact_motion, script_graph_summary
from .motions import read_figatree
from .techs import TECH_LABELS, tech_label
from .movement import JUMP_PHASE_IDS, movement_label, movement_visibility, read_jump_parameters, jump_duration


CATALOG = 'attack-catalog.json'
COPY_NAMES = dict(Mr='Mario', Lk='Link', Ss='Samus', Ys='Yoshi', Fx='Fox', Pk='Pikachu',
                  Lg='Luigi', Ca='Captain Falcon', Ns='Ness', Kp='Bowser', Pe='Peach',
                  Pp='Ice Climbers', Dk='Donkey Kong', Zd='Zelda', Sk='Sheik', Pr='Jigglypuff',
                  Mt='Mewtwo', Ms='Marth', Gw='Mr. Game & Watch', Fc='Falco', Cl='Young Link',
                  Dr='Dr. Mario', Pc='Pichu', Gn='Ganondorf', Fe='Roy')
NORMAL_LABELS = {
    'Attack11':'Jab 1', 'Attack12':'Jab 2', 'Attack13':'Jab 3',
    'Attack100Start':'Rapid jab — startup', 'Attack100Loop':'Rapid jab — loop', 'Attack100End':'Rapid jab — ending',
    'AttackDash':'Dash attack', 'AttackHi3':'Up tilt', 'AttackLw3':'Down tilt',
    'AttackHi4':'Up smash', 'AttackLw4':'Down smash',
    'Catch':'Grab', 'CatchDash':'Dash grab', 'CatchWait':'Grab — hold', 'CatchAttack':'Pummel', 'CatchCut':'Grab — release',
    'AirCatch':'Tether aerial (Z-air)', 'AirCatchHit':'Tether aerial — hit/retract',
    'ThrowF':'Forward throw', 'ThrowB':'Back throw', 'ThrowHi':'Up throw', 'ThrowLw':'Down throw',
    'DownAttackU':'Getup attack — face up', 'DownAttackD':'Getup attack — face down',
    'CliffAttackQuick':'Ledge attack — below 100%', 'CliffAttackSlow':'Ledge attack — 100%+',
}


def attack_label(name):
    """Only attacking actor motions; exclude capture/victim reaction clips."""
    if name in NORMAL_LABELS:
        return NORMAL_LABELS[name], 'Normals / grabs'
    for prefix, label in [('AttackS3', 'Forward tilt'), ('AttackS4', 'Forward smash')]:
        if name.startswith(prefix):
            suffix = name[len(prefix):]
            return label + {'Hi':' — high', 'HiS':' — slightly high', 'Lw':' — low',
                            'LwS':' — slightly low', 'S':'', '':''}.get(suffix, ' — '+suffix), 'Normals / grabs'
    match = re.fullmatch(r'(AttackAir|LandingAir)(N|F|B|Hi|Lw)', name)
    if match:
        label = dict(N='Neutral air', F='Forward air', B='Back air', Hi='Up air', Lw='Down air')[match[2]]
        return label + (' — landing' if match[1] == 'LandingAir' else ''), 'Aerials'
    match = re.fullmatch(r'([A-Za-z]{2})?(Special)(Air)?(N|S|Hi|Lw)(.*)', name)
    if match:
        copy, _, air, direction, suffix = match.groups()
        if copy and copy not in COPY_NAMES:
            return None
        if suffix.startswith('Air'):
            air, suffix = 'Air', suffix[3:]
        label = dict(N='Neutral special', S='Side special', Hi='Up special', Lw='Down special')[direction]
        label += ' — aerial' if air else ' — grounded'
        if suffix:
            label += ' — ' + re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', suffix).replace('Cansel','Cancel').lower()
        if copy:
            label = f'Kirby copy: {COPY_NAMES[copy]} — {label}'
        return label, 'Copied specials' if copy else 'Specials'
    if not name.endswith('Damage') and re.match(r'^(?:LightThrow|HeavyThrow|.*Swing|ItemShoot|ItemHammer|ItemScrew)', name):
        return 'Item attack — '+re.sub(r'(?<=[a-z])(?=[A-Z0-9])', ' ', name), 'Item attacks'
    return None


def common_submotions(repo):
    text = (repo/'src/melee/ft/kinds/ftCommon/forward.h').read_text()
    body = text.split('typedef enum ftCo_Submotion {', 1)[1].split('}', 1)[0]
    result, value = {}, -2
    for name, assigned in re.findall(r'ftCo_SM_(\w+)\s*(?:=\s*(-?\d+))?\s*[,\n]', body):
        value = int(assigned) if assigned else value + 1
        result[value] = name
    return result


def sample_times(period, looping, fps=50):
    count = max(1, math.ceil(period/60*fps))
    times = [period*i/count for i in range(count)]
    return times if looping else times+[period]


def build_attack_catalog(repo, report):
    from .roster import roster
    repo = Path(repo).resolve()
    files = repo/'orig/GALE01/files'
    fighters = roster(files,include_extra=True)['fighters']
    from .extra_fighters import prepare_extra_models,hand_submotions,hand_action,readable
    prepare_extra_models(repo,fighters)
    tables = {t['fighter_kind']: t for t in report['normal_tables']}
    sources = {}
    for fighter in fighters:
        kind = fighter['fighter_kind']; table = tables[kind]
        archive = Archive((files/table['fighter_archive']).read_bytes())
        sources[kind] = (table, archive, motion_entries(archive, table['fighter_root'], 12, table['motion_count']))
    dol_bytes = (repo/'orig/GALE01/sys/main.dol').read_bytes()
    if hashlib.sha1(dol_bytes).hexdigest() != report['dol_sha1']:
        raise ValueError('Original DOL no longer matches the inspected motion report')
    dol = Dol(dol_bytes)
    sizes = read_global(dol, load_symbols(repo/'config/GALE01/symbols.txt'), 'ftAction_803C0870')
    common = common_submotions(repo)
    regions, entries = {}, []
    for primary in fighters:
        if primary['paired_member']:
            continue
        slug, label = ALL_CHARACTERS[primary['character_kind']]
        companion = next((f for f in fighters if f['paired_member'] and f['character_kind']==primary['character_kind']), None)
        kind = primary['fighter_kind']; _, _, motions = sources[kind]
        expected_nodes = json.loads((repo/'build/melee_anim/exported'/slug/'costume_00/model.json').read_text())['bones']
        hand_names=hand_submotions(repo,kind,next(k for k,v in common.items() if v=='Count')) if kind in (27,28) else None
        actions = []
        for motion in motions:
            if not motion['size']:
                continue
            name = motion['symbol'].split('_ACTION_')[-1].removesuffix('_figatree')
            semantic = common.get(motion['animation_id'], name)
            # ftSs_Submotion / MotionStateTable name the two misspelled DAT
            # symbols Special / SpecialAir as the smash-input missile clips.
            if kind == 13 and name in ('Special','SpecialAir'):
                semantic = 'SpecialSSmash' if name == 'Special' else 'SpecialAirSSmash'
            recovery = tech_label(semantic)
            locomotion=movement_label(motion['animation_id'],name,kind)
            chosen = (locomotion,'Movement') if locomotion else (recovery[0], 'Ground recovery') if recovery else attack_label(semantic)
            if chosen is None:
                chosen = attack_label(name)
            category = 'movement' if locomotion else 'tech' if recovery else 'attack'
            if hand_names is not None:
                category,title,group=hand_action(hand_names[motion['animation_id']])
                chosen=(title,group)
            elif kind>=27 and chosen is None:
                category='hit' if kind==32 else 'taunt' if name.startswith('Appeal') else 'other'
                chosen=('Taunt' if category=='taunt' else readable(name),'Hit' if category=='hit' else 'Other')
            if chosen is None:
                continue
            from .held_items import item_for_motion
            prop=item_for_motion(f'attack-{motion["animation_id"]}',kind) if category=='attack' else None
            from .character_props import character_prop, resolve_profile
            special=resolve_profile(files,report,character_prop(kind,name)) if category=='attack' else None
            from .character_effects import character_effects
            effects=character_effects(kind,name) if category=='attack' else []
            if prop:
                suffix=(('Jab','Tilt','Smash','Dash attack','Smash follow-up')[prop['variant']] if 'variant' in prop else common.get(motion['animation_id'],name))
                chosen=(prop['name']+' — '+suffix,'Item attacks')
            actors = []
            reason = None
            for member in [primary] + ([companion] if companion else []):
                member_kind = member['fighter_kind']; source_kind = member_kind
                table, archive, member_motions = sources[source_kind]
                aid = motion['animation_id']
                selected = member_motions[aid] if aid < len(member_motions) else None
                # Nana's ordinary empty slots explicitly reuse Popo's clips.
                if (not selected or not selected['size']) and member_kind == 11:
                    source_kind = 10; table, archive, member_motions = sources[10]; selected = member_motions[aid]
                if not selected or not selected['size']:
                    reason = 'Companion motion is unavailable'; break
                if source_kind not in regions:
                    regions[source_kind] = (files/table['animation_file']).read_bytes()
                packed = read_exact_motion(regions[source_kind], selected, table['animation_file'])
                metadata, tracks = read_figatree(packed, selected['symbol'])
                nodes = len(expected_nodes) if not member['paired_member'] else len(json.loads((repo/'build/melee_anim/exported'/slug/'costume_00/companion/model.json').read_text())['bones'])
                if metadata['node_count'] != nodes and not (kind==4 and metadata['node_count'] in (46,48,50,53)):
                    reason = 'This clip requires a different character model'; break
                if metadata['type'] not in (0,1) or set(metadata['channels'])-{1,2,3,5,6,7,8,9,10,11,12}:
                    reason = 'This clip needs additional animation channel support'; break
                actors.append({'fighter_kind':member_kind, 'source_fighter_kind':source_kind,
                               'visibility_override':movement_visibility(member_kind,aid) if category=='movement' else None,
                               'character_prop':special,
                               'character_effects':effects,
                               'animation_file':table['animation_file'], 'clip':{**selected, **metadata,
                               'effective_loop':metadata['tree_loop'] or selected['motion_loop'],
                               'script':script_graph_summary(archive, selected['script_offset'], sizes)}})
                if category=='movement' and aid in (207,208):
                    initial=[]
                    for previous in range(206,aid):
                        earlier=member_motions[previous]
                        if not earlier['size']:continue
                        meta,_=read_figatree(read_exact_motion(regions[source_kind],earlier,table['animation_file']),earlier['symbol'])
                        initial.append((script_graph_summary(archive,earlier['script_offset'],sizes),meta['frames']))
                    actors[-1]['texture_initial_scripts']=initial
            prefix='other' if category in ('taunt','hit') else category
            loop_duration={}
            if reason is None and effects and actors[0]['clip']['effective_loop']:
                from .character_effects import shared_loop_period
                duration=shared_loop_period(actors[0]['clip']['frames'],effects)
                for actor in actors:actor['effect_loop_duration']=duration
                loop_duration={'duration_ticks':duration}
            actions.append({'key':f'{prefix}-{motion["animation_id"]}_source', 'animation_id':motion['animation_id'],
                            'animation_type':category, 'ground_effect':recovery[1] if recovery else None,
                            'name':name, 'label':chosen[0], 'group':chosen[1], 'actors':actors,
                            'held_item':prop or special,
                            'character_effects':effects,
                            'available':reason is None, 'unavailable_reason':reason,**loop_duration})
        # Full/short hops share JumpF but have distinct source launch velocities.
        has_jump=all(aid<len(motions) and motions[aid]['size'] for aid in JUMP_PHASE_IDS.values())
        for mode,title in ([('fullhop','Full hop'),('shorthop','Short hop')] if has_jump else []):
            actors=[]
            for member in [primary]+([companion] if companion else []):
                mk=member['fighter_kind'];sk=10 if mk==11 else mk
                table,archive,member_motions=sources[sk];phases={}
                if sk not in regions:regions[sk]=(files/table['animation_file']).read_bytes()
                blob=regions[sk]
                for phase,aid in JUMP_PHASE_IDS.items():
                    selected=member_motions[aid]
                    if not selected['size']:raise ValueError(f'Missing grounded jump phase {slug}/{mk}/{phase}')
                    metadata,_=read_figatree(read_exact_motion(blob,selected,table['animation_file']),selected['symbol'])
                    phases[phase]={**selected,**metadata}
                own_table,own_archive,_=sources[mk]
                parameters=read_jump_parameters(own_archive,own_table['fighter_root'])
                duration=jump_duration(parameters,mode,phases['landing']['frames'])
                actors.append({'fighter_kind':mk,'source_fighter_kind':sk,'animation_file':table['animation_file'],
                               'clip':{**phases['jump'],'effective_loop':False},'movement':{'mode':mode,'parameters':parameters,'phases':phases,'duration_ticks':duration}})
            duration=max(a['movement']['duration_ticks'] for a in actors)
            for actor in actors:actor['render_duration']=duration
            actions.append({'key':f'movement-{mode}_source','animation_type':'movement','animation_id':16,'name':mode,'label':title,'group':'Movement',
                            'ground_effect':None,'actors':actors,'duration_ticks':duration,'available':True,'unavailable_reason':None})
        from .sequences import combined_actions
        actions.extend(combined_actions(actions, kind))
        counts = Counter(a['label'] for a in actions)
        used = Counter()
        for a in actions:
            if counts[a['label']] > 1:
                used[a['label']] += 1
                a['label'] += f' — variant {used[a["label"]]}'
        order = {name:i for i,name in enumerate(TECH_LABELS)}
        actions.sort(key=lambda a:(a['animation_type']=='tech',order.get(common.get(a['animation_id']),-1)))
        entries.append({'character':slug, 'character_label':label, 'costumes':primary['costumes'],
                        'fighter_kind':kind, 'actions':actions})
        print(f'{label}: {sum(a["available"] and a["animation_type"]=="attack" for a in actions)} attacks, '
              f'{sum(a["available"] and a["animation_type"]=="movement" for a in actions)} movements, '
              f'{sum(a["available"] and a["animation_type"]=="tech" for a in actions)} tech/ground clips; '
              f'{sum(not a["available"] for a in actions)} unavailable', flush=True)
    return {'schema':'melee_anim.attacks.v1', 'dol_sha1':report['dol_sha1'], 'characters':entries,
            'limitations':['Isolated source poses with six common held weapons; no opponent, projectiles, charge inputs or full game physics; Tech impact meshes are optional',
                           'Combined multipart choices are finite source-phase presets, not complete game controllers']}


def virtual_clips(root):
    path = Path(root)/CATALOG
    if not path.is_file():
        return []
    from .roster import color_label
    result = []
    for fighter in json.loads(path.read_text())['characters']:
        for action in fighter['actions']:
            if not action['available']:
                continue
            clip = action['actors'][0]['clip']
            for costume in fighter['costumes']:
                cid = costume['costume_id']; slug = fighter['character']
                color = color_label(costume, fighter['fighter_kind'])
                period=action.get('duration_ticks',clip['frames'])
                times = sample_times(period, clip['effective_loop'])
                filename = f'{slug}-{action["key"].replace("_","-")}-costume-{cid:02d}-{color.split()[0].lower()}.gif'
                result.append({'character':slug, 'character_label':fighter['character_label'],
                               'action_key':action['key'], 'action_label':action['label'], 'animation_type':action.get('animation_type','attack'),
                               'ground_effect':action.get('ground_effect'),
                               'held_item':action.get('held_item'),
                               'sequence':action.get('sequence'),
                               'character_effects':action.get('character_effects'),
                               'costume_id':cid, 'costume_label':color, 'fps':50, 'period':period,
                               'authored_loop':clip['effective_loop'], 'symbol':clip['symbol'],
                               'frame_count':len(times), 'download_name':filename, 'frames':[], 'source_times':[],
                               'gif':'', 'lazy':True})
    return result


def find_action(catalog, kind, action):
    for fighter in catalog['characters']:
        if fighter['fighter_kind'] == kind or kind == 11 and fighter['fighter_kind'] == 10:
            selected = next((a for a in fighter['actions'] if a['key']==action+'_source' and a['available']), None)
            if selected:
                return next(a for a in selected['actors'] if a['fighter_kind']==kind)
    raise ValueError('Unknown or unsupported attack clip')


class AttackCache:
    def __init__(self, root, repo=None):
        self.root = Path(root).resolve()
        self.repo = Path(repo).resolve() if repo else Path(__file__).resolve().parents[2]
        self.lock = threading.RLock()

    def get(self, clip, effects=False):
        if not clip.get('lazy'):
            return clip
        with self.lock:
            model = self.repo/'build/melee_anim/exported'/clip['character']/f'costume_{clip["costume_id"]:02d}/model.json'
            companion = model.parent/'companion/model.json'
            catalog = self.root/CATALOG
            selection = json.loads(catalog.read_text())
            action = clip['action_key'].rsplit('_',1)[0]
            effects = bool(effects and clip.get('ground_effect'))
            paths = [catalog, model, self.repo/'build/melee_anim/motions.json']
            actor=find_action(selection,json.loads(model.read_text()).get('fighter_kind'),action)
            from .character_effects import effect_archives
            paths.extend(self.repo/'orig/GALE01/files'/archive for archive in effect_archives(actor))
            from .sequences import prop_archives
            for archive in prop_archives(actor):
                paths.extend([self.repo/'orig/GALE01/files'/archive,self.repo/'orig/GALE01/files/PlCo.dat'])
            from .held_items import item_for_motion, item_archive
            if item_for_motion(action,json.loads(model.read_text()).get('fighter_kind')):
                paths.extend([item_archive(self.repo/'orig/GALE01/files'),self.repo/'orig/GALE01/files/PlCo.dat'])
                for source in [model]+([companion] if companion.is_file() else []):
                    kind=json.loads(source.read_text())['fighter_kind']
                    table=next(t for t in json.loads(paths[2].read_text())['normal_tables'] if t['fighter_kind']==kind)
                    paths.append(self.repo/'orig/GALE01/files'/table['fighter_archive'])
            if action.startswith('tech-'):
                paths.append(self.repo/'orig/GALE01/files/EfCoData.dat')
                paths.append(self.repo/'orig/GALE01/files/PlCo.dat')
            for source in [model]+([companion] if companion.is_file() else []):
                data = json.loads(source.read_text()); actor = find_action(selection, data['fighter_kind'], action)
                paths += [source, self.repo/'orig/GALE01/files'/actor['animation_file']]
                paths += [self.repo/'orig/GALE01/files'/p['animation_file'] for p in actor.get('sequence',{}).get('phases',[])]
                paths += [source.parent/t['image_file'] for m in data['materials'] for t in m['textures'] if t.get('image_file')]
            paths += list(Path(__file__).parent.glob('*.py'))
            size=native_size(clip['action_key'],clip.get('animation_type'))
            digest = hashlib.sha256(f'attack-v3-{size}px-50fps-60ticks'.encode())
            digest.update(repr((clip['character'],clip['costume_id'],action,effects)).encode())
            for path in sorted(set(paths)):
                digest.update(str(path).encode()); digest.update(hashlib.sha256(path.read_bytes()).digest())
            folder = self.root/'attacks'/digest.hexdigest(); marker = folder/'complete.json'
            expected = {f'frame_{i:04d}.png' for i in range(clip['frame_count'])} | {'preview.gif','preview-manifest.json'}
            ready = False
            if marker.is_file():
                try:
                    hashes = json.loads(marker.read_text())
                    ready = set(hashes)==expected and all((folder/n).is_file() and hashlib.sha256((folder/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
                except (ValueError,OSError,TypeError,AttributeError):
                    pass
            if not ready:
                folder.mkdir(parents=True,exist_ok=True)
                command = [sys.executable,'-m','tools.melee_anim.preview','--model',str(model),'--action',action,
                           '--attack-catalog',str(catalog),'--output',str(folder),'--size',str(size),'--backend','native' if os.name=='nt' else 'python']
                if companion.is_file():
                    command += ['--companion',str(companion)]
                if action.startswith('tech-'):
                    command += ['--ground-effects','on' if effects else 'off']
                with (folder/'render.log').open('w') as log:
                    result = subprocess.run(command,cwd=self.repo,stdout=log,stderr=subprocess.STDOUT,timeout=600,
                                            env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
                if result.returncode or not all((folder/n).is_file() for n in expected):
                    raise RuntimeError('Attack rendering failed; see '+str(folder/'render.log'))
                manifest = json.loads((folder/'preview-manifest.json').read_text())
                if len(manifest['sample_source_times']) != clip['frame_count']:
                    raise RuntimeError('Attack render changed the expected timeline')
                hashes = {n:hashlib.sha256((folder/n).read_bytes()).hexdigest() for n in sorted(expected)}
                temporary = marker.with_suffix('.tmp'); temporary.write_text(json.dumps(hashes)); temporary.replace(marker)
            manifest = json.loads((folder/'preview-manifest.json').read_text())
            relative = folder.relative_to(self.root).as_posix()
            name = clip['download_name'].replace('.gif','-ground-effects.gif') if effects else clip['download_name']
            return {**clip,'download_name':name,'ground_effects_enabled':effects,
                    'frames':[f'{relative}/frame_{i:04d}.png' for i in range(clip['frame_count'])],
                    'source_times':manifest['sample_source_times'],'gif':f'{relative}/preview.gif'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('build/melee_anim/preview'))
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    report = json.loads((repo/'build/melee_anim/motions.json').read_text())
    catalog = build_attack_catalog(repo, report)
    args.root.mkdir(parents=True,exist_ok=True)
    (args.root/CATALOG).write_text(json.dumps(catalog,separators=(',',':'))+'\n')
    print(f'Cataloged {len(virtual_clips(args.root))} attack/tech costume choices', flush=True)


if __name__=='__main__':
    main()
