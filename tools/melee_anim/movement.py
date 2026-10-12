"""Movement identities and a focused neutral ground-jump preview preset.

Jump squat/pose/fall/landing are original clips. Full/short hops differ in
original launch velocity; no horizontal input, fast fall, slope or stage AI.
"""
import math
from pathlib import Path

from .hsd import Archive, FormatError
from .inspect_motions import read_exact_motion
from .motions import read_figatree

MOVEMENT_IDS={2:'Standing',7:'Walking — slow',8:'Walking — medium',9:'Walking — fast',12:'Dashing',13:'Running',
              41:'Spot dodge',42:'Roll forward',43:'Roll backward',
              206:'Sleep — falling asleep',207:'Sleep — sleeping',208:'Sleep — waking up'}
JUMP_PHASE_IDS={'squat':15,'jump':16,'fall':20,'landing':34,'standing':2}


def movement_label(aid,name,kind=None):
    if kind==14 and aid==37:
        return 'Yoshi egg'
    if aid in MOVEMENT_IDS:
        return MOVEMENT_IDS[aid]
    if aid in (3,4,5) and name.startswith('Wait') and name!='WaitItem':
        return f'Idle {aid-2}'
    return None


def movement_visibility(kind,aid):
    # ftCo_80099438 selects Yoshi's egg for rolls; ftCo_80099954 restores
    # the normal body for spot dodge. GuardOn supplies the allowed egg pose.
    return {0:1} if kind==14 and aid in (37,42,43) else None


def movement_visibility_timeline(model,motion,initial=None):
    """Source model-part commands, including Samus's ball transition."""
    from .held_items import script_events
    defaults=model.get('visibility',{}).get('defaults')
    if defaults is None:return []
    states=(defaults if initial is None else initial).copy()
    for group,value in motion.get('visibility_override',{}).items():states[int(group)]=value
    timeline=[(0,states.copy())]
    script=motion.get('script',{})
    if not any('visibility_group' in cmd for block in [script]+script.get('reachable_blocks',[]) for cmd in block.get('commands',[])):
        return timeline
    for tick,command in script_events(script,motion['frames']):
        if 'visibility_group' not in command:continue
        group=command['visibility_group']
        if not 0<=group<len(states):raise ValueError('Dodge visibility group is outside the model')
        states[group]=command['visibility_value'];timeline.append((tick,states.copy()))
    return timeline


def read_jump_parameters(ar,root):
    attrs=ar.pointer(ar.public(root))
    fields={'startup':0x38,'full_velocity':0x40,'short_velocity':0x4C,'gravity':0x5C,'terminal_velocity':0x60}
    result={k:ar.f32(attrs+offset) for k,offset in fields.items()}
    if any(not math.isfinite(v) or v<=0 for v in result.values()):
        raise FormatError('Invalid grounded jump parameters')
    return result


def flight_heights(velocity,gravity,terminal):
    """Fixed game-tick integration: first jump Phys skips gravity, then clamp."""
    if any(not math.isfinite(v) or v<=0 for v in (velocity,gravity,terminal)):
        raise ValueError('Jump velocity/gravity/terminal must be finite and positive')
    height=0.;values=[height]
    for tick in range(1,1001):
        if tick>1:velocity=max(velocity-gravity,-terminal)
        height+=velocity
        if height<=0:
            values.append(0.)
            return values
        values.append(height)
    raise ValueError('Neutral jump exceeds bounded flight duration')


def jump_duration(parameters,mode,landing_frames):
    return math.ceil(parameters['startup'])+len(flight_heights(parameters['short_velocity' if mode=='shorthop' else 'full_velocity'],parameters['gravity'],parameters['terminal_velocity']))-1+landing_frames


def is_jump(action):
    return action.removesuffix('_source') in ('movement-fullhop','movement-shorthop')


def centered_jump_setting(action, value):
    if value not in ('on', 'off') or value == 'on' and not is_jump(action):
        raise ValueError('Keep character centered is only available for full/short hops')
    return value == 'on'


class JumpScene:
    def __init__(self,actor,files,mode,remap=None):
        self.parameters=actor['movement']['parameters'];self.mode=mode
        self.phases={}
        blob=(Path(files)/actor['animation_file']).read_bytes()
        for name,motion in actor['movement']['phases'].items():
            metadata,tracks=read_figatree(read_exact_motion(blob,motion,actor['animation_file']),motion['symbol'])
            if remap:tracks=remap(tracks,metadata['node_count'])
            self.phases[name]=(metadata,tracks)
        self.startup=math.ceil(self.parameters['startup'])
        self.heights=flight_heights(self.parameters['short_velocity' if mode=='shorthop' else 'full_velocity'],self.parameters['gravity'],self.parameters['terminal_velocity'])
        self.flight=len(self.heights)-1
        self.duration=self.startup+self.flight+self.phases['landing'][0]['frames']

    def sample(self,tick):
        if tick<self.startup:
            phase,time,height='squat',tick,0.
        elif tick<self.startup+self.flight:
            t=tick-self.startup;index=math.floor(t);fraction=t-index
            height=self.heights[index]*(1-fraction)+self.heights[index+1]*fraction
            jump_period=self.phases['jump'][0]['frames']
            phase,time=('jump',t) if t<jump_period else ('fall',(t-jump_period)%self.phases['fall'][0]['frames'])
        elif tick<self.duration:
            phase,time,height='landing',tick-self.startup-self.flight,0.
        else:
            phase,time,height='standing',0.,0.
        meta,tracks=self.phases[phase]
        return meta,tracks,min(time,meta['frames']),height

    def provenance(self):
        return {'mode':self.mode,'parameters':self.parameters,'startup_ticks':self.startup,'flight_ticks':self.flight,'peak_height':max(self.heights),
                'phases':{name:meta['frames'] for name,(meta,_) in self.phases.items()},
                'policy':'neutral flat-plane jump; source launch velocity/gravity/terminal; one first-physics grace tick',
                'limitations':['Isolated preset, not full fighter input/collision/state simulation','No horizontal drift, fast fall, slopes, landing effects or procedural dynamics','No transition blending or emulator-reference validation']}
