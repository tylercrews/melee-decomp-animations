"""Non-playable fighter presentation; identities come from original tables."""
import re
from pathlib import Path


def hand_submotions(repo, kind, common_count):
    directory, prefix = ('ftMasterHand','ftMh') if kind==27 else ('ftCrazyHand','ftCh')
    text=(Path(repo)/'src/melee/ft/kinds'/directory/'forward.h').read_text()
    body=text.split(f'typedef enum {prefix}_Submotion {{',1)[1].split('}',1)[0]
    value=common_count-1;result={}
    for name,assigned in re.findall(prefix+r'_SM_(\w+)\s*(?:=\s*([^,]+))?,',body):
        if name in ('Count','SelfCount'):break
        value=common_count if assigned.strip()=='ftCo_SM_Count' else int(assigned) if assigned else value+1
        result[value]=name
    return result


def readable(name):
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])',' ',name).replace('_',' ')


def hand_action(name):
    # These are boss animation IDs, not the common ground movement table.
    if re.fullmatch(r'Wait[12]_\d+',name):
        family,variant=name.split('_')
        return 'movement',f'{"Standing" if family=="Wait1" else "Idle"} — variant {int(variant)+1}','Movement'
    if name.startswith(('Damage','Entry')) or name in ('Cancel','Fail','TagFail','TagCancel','BackDisappear'):
        return 'other',readable(name),'Other'
    return 'attack',readable(name),'Boss attacks'


def prepare_extra_models(repo, fighters):
    """Use the existing exporter; six actual costume entries, no fake colors."""
    from .catalog import ALL_CHARACTERS
    from .export_model import export_fighter
    repo=Path(repo)
    for fighter in fighters:
        if fighter['fighter_kind']<27:continue
        slug,_=ALL_CHARACTERS[fighter['character_kind']]
        for costume in fighter['costumes']:
            export_fighter(repo/'orig/GALE01/files',
                           repo/'build/melee_anim/exported'/slug/f"costume_{costume['costume_id']:02d}",
                           fighter['fighter_kind'],costume['costume_id'])
