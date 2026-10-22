"""Semantic all-character batch families, independent of fighter motion IDs."""
import re


def slug(value):
    return re.sub(r'[^a-z0-9]+','-',value.lower()).strip('-')


def family(action):
    category=action.get('animation_type','attack');label=action.get('label',action['key'])
    if category=='taunt':return 'taunt','taunts'
    if category=='victory':return 'victory','victory poses'
    if category=='clapping':return 'clapping','clapping'
    if category=='attack':
        copy=re.match(r'Kirby copy: (.+?) \u2014 ((?:Neutral|Side|Up|Down) special)',label)
        if copy:return 'attack:copy-'+slug(copy[1]+' '+copy[2]),copy[1]+' copy '+copy[2]
        title=label.split(' \u2014 ')[0]
        if title=='Item attack':title=label
        prop=action.get('held_item') or {}
        if 'item_kind' in prop and 'variant' in prop:
            title=prop['name']+' '+('Jab','Tilt','Smash','Dash attack','Smash follow-up')[prop['variant']]
    elif category=='tech':
        title=label.split(' \u2192 ')[0]
    else:title=re.sub(r' \u2014 variant \d+$','',label)
    return category+':'+slug(title),title


def metadata(catalog):
    result={}
    for character in catalog.get('characters',[]):
        actions=[a for a in character['actions'] if a.get('available')]
        families={a['key']:family(a) for a in actions}
        covered=set()
        for action in actions:
            if not action.get('sequence'):continue
            phase_ids={p['clip']['animation_id'] for p in action['actors'][0]['sequence']['phases']}
            for candidate in actions:
                if candidate.get('sequence'):continue
                if families[candidate['key']][0]==families[action['key']][0] and candidate['animation_id'] in phase_ids:
                    covered.add(candidate['key'])
            if character.get('fighter_kind')==4 and action['animation_id'] in (324,328):
                covered.update(a['key'] for a in actions if not a.get('sequence') and 324<=a['animation_id']<=331)
        for action in actions:
            key,title=families[action['key']]
            result[(character['character'],action['key'])]={'batch_family':key,'batch_label':title,
                'batch_partial':action['key'] in covered,'animation_type':action.get('animation_type','attack')}
    return result


def enrich(clips,catalog):
    lookup=metadata(catalog)
    result=[]
    for clip in clips:
        action=clip['action_key']
        extra=lookup.get((clip['character'],action))
        if extra is None:
            if action.startswith('victory'):key,title,kind='victory','victory poses','victory'
            elif action=='results-clap_source':key,title,kind='clapping','clapping','clapping'
            elif action=='taunt_source':key,title,kind='taunt','taunts','taunt'
            else:
                kind=clip.get('animation_type','attack');title=clip.get('action_label',action)
                key=kind+':'+slug(title)
            extra={'batch_family':key,'batch_label':title,'animation_type':kind,'batch_partial':False}
        result.append({**clip,**extra})
    return result


def select_all(clips,character,action):
    selected=next((c for c in clips if c['character']==character and c['action_key']==action),None)
    if selected is None:raise ValueError('Unknown batch animation')
    family_key=selected['batch_family']
    return [c for c in clips if c['batch_family']==family_key and not c['batch_partial']],selected['batch_label']
