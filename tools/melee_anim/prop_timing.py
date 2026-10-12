"""Bounded source item-script timing and state-owned prop visibility.

Item commands differ from fighter commands. In particular item opcodes 17..19
set three separate variables (itanimlist.c); fighter opcode 19 is unrelated.
This evaluates timing/control flow, not hitboxes, sound, particles or physics.
"""
from .hsd import FormatError

VERSION=1


def needs_current_master(kind,action,section):
    """Old prebuilt families affected by the source visibility audit.

    Other prebuilt masters keep identical draw selections. Ordinary, powered
    and rotated clips already fingerprint the renderer and original archives.
    """
    return ((kind==10 and action!='taunt') or
            (kind in (20,24) and action=='taunt') or
            (section=='source' and (kind,action) in ((5,'victory3'),(6,'victory3'),(18,'victory2'))))


def item_script_events(ar, start, duration):
    pc=start;tick=0.;returns=[];loops=[];events=[]
    for _ in range(8192):
        if pc is None or tick>duration:break
        word=ar.u32(pc);op=word>>26;value=word&0x3ffffff
        if op>25:raise FormatError(f'Unsupported item script opcode {op}')
        count=2 if op in (5,7) else 5 if op==10 else 7 if op==11 else 1
        if op==16:
            sub=(word>>18)&255
            if sub not in (0,1,2,10,11):raise FormatError(f'Unsupported item sound command {sub}')
            count=3 if sub<3 else 2
        ar.read(pc,count*4);next_pc=pc+count*4
        if op==0:break
        if op==1:tick+=value
        elif op==2:tick=max(tick,value)
        elif op==3:loops.append([next_pc,value])
        elif op==4 and loops:
            loops[-1][1]-=1
            if loops[-1][1]>0:next_pc=loops[-1][0]
            else:loops.pop()
        elif op==5:returns.append(next_pc);next_pc=ar.pointer(pc+4)
        elif op==6:
            if not returns:break
            next_pc=returns.pop()
        elif op==7:next_pc=ar.pointer(pc+4)
        elif op==8:
            # Command_08 waits for an animation wrap, not zero elapsed time.
            # Only the current authored item interval is evaluated here.
            break
        elif op in (17,18,19):events.append((tick,op-17,value))
        pc=next_pc
    else:raise FormatError('Item script exceeds bounded commands')
    return events


def fighter_prop_visibility(spec, duration, events):
    """Source callbacks, independent of authored joint visibility tracks."""
    behavior=spec.get('behavior');visible=[(0,True)]
    if behavior in ('hammer','milk') or 'spawn_variable' in spec:visible=[(0,False)]
    for tick,cmd in events:
        var=cmd.get('command_variable')
        if not var:continue
        index,value=var['index'],var['value']
        if 'spawn_variable' in spec and index==spec['spawn_variable'] and value==1:visible.append((tick,True))
        elif behavior=='blaster' and 'End' in spec.get('phase','') and index==1:
            visible.append((tick,value==1))  # it_802ADDD0: BOTH 0 and 2 hide.
        elif behavior=='hammer' and index==0 and value in (1,2):visible.append((tick,value==1))
        elif behavior=='milk' and index==1 and value in (1,2):visible.append((tick,value==1))
    if behavior=='game-watch' and spec.get('phase')==62:
        visible=[(0,False),(3,True)]  # itGamewatchFire_Motion0_Anim
    if behavior=='game-watch' and spec.get('phase')==68:visible.append((30,False))
    if behavior=='toad':
        visible=[(0,False),(7,True),(53,False)] if spec['animation_id']==0 else [(0,True),(60,False)]
    if behavior=='bow' and spec['animation_id'] in (2,5):visible.append((24,False))
    # State-owned articles are destroyed on leaving the last action. Common
    # held weapons persist; separate free-flight needles use their own life.
    phase=spec.get('phase','')
    retained=(behavior in ('blaster','bow') and 'End' not in phase or
              behavior=='needles' or
              behavior=='cutter' and phase.endswith(('1','2','3')) or
              behavior=='peach-parasol' or
              behavior=='game-watch' and phase in (49,50))
    if behavior and behavior!='needle-release' and not retained and not spec.get('continues_next_phase'):
        visible.append((duration,False))
    return sorted(visible,key=lambda event:event[0])


def blaster_slide(phase, events, frame):
    """it_802AE538/608/63C: original five-position draw/holster slide."""
    index=4 if 'End' in phase else 0
    for tick,cmd in events:
        var=cmd.get('command_variable')
        if not var or var['index']!=3 or tick>frame:continue
        elapsed=int(frame-tick)
        if var['value']==1:index=min(4,1+elapsed)
        elif var['value']==2:index=max(0,3-elapsed)
    return (-.425,-.595,-.765,-.935,-.85)[index]
