"""Source article slots and runtime model-part presets for Game & Watch."""
def prop_profile(aid):
    profiles={46:(0,32,0,'Insecticide spray'),49:(0,32,1,'Insecticide spray'),
              50:(0,32,2,'Insecticide spray'),51:(0,32,3,'Insecticide spray'),
              59:(1,32,0,'Manhole cover'),62:(2,32,0,'Torch'),
              68:(3,1,0,'Parachute'),70:(4,17,0,'Turtle'),71:(5,21,0,'Air puff'),
              319:(7,0,0,'Oil spill'),322:(7,0,1,'Oil spill'),
              315:(9,0,0,'Fire rescue'),316:(9,0,0,'Fire rescue')}
    if 297<=aid<=314:
        number=(aid-297)%9+1
        return dict(special=True,item_kind=-1,name=f'Judgment {number} sign',article_slot=6,
                    asset_fighter_kind=24,canonical_part=49,animation_id=0,
                    behavior='game-watch',judge_number=number,frozen_frame=number,spawn_variable=1)
    if aid not in profiles:return None
    slot,joint,anim,label=profiles[aid]
    result=dict(special=True,item_kind=-1,name=label,article_slot=slot,asset_fighter_kind=24,
                raw_joint=joint,animation_id=anim,behavior='game-watch',phase=aid)
    if aid in (315,316):result.update(spawn_variable=0)
    return result


def visibility_timeline(model,motion,aid):
    """Timed source commands plus Oil Panic's callback-selected bucket state."""
    from .movement import movement_visibility_timeline
    motion=dict(motion)
    if aid in (317,318,319,320,321,322):
        # Standalone catch receives one charge. ReleaseOil clears charge before
        # UpdateBucketModel, so the shooting bucket has empty indicators.
        filled=1 if aid in (318,321) else 0
        motion['visibility_override']={5:2,**{6+i:0 if i<filled else -1 for i in range(3)}}
    timeline=movement_visibility_timeline(model,motion)
    if aid in (317,320):
        from .held_items import script_events
        states=model['visibility']['defaults'].copy();timeline=[(0,states.copy())]
        for tick,c in script_events(motion.get('script',{}),motion['frames']):
            var=c.get('command_variable')
            if var=={'index':0,'value':1}:states[5]=2
            if 'visibility_group' in c:states[c['visibility_group']]=c['visibility_value']
            if var or 'visibility_group' in c:timeline.append((tick,states.copy()))
    return timeline
