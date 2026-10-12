"""Source-confirmed attached character articles, separate from common items.

Profiles identify ftData.x48 article slots or effect descriptors. They do not
implement projectile trajectories, collisions or a complete fighter controller.
"""
def character_prop(kind, name, animation_id=None):
    if kind==24:
        from .game_watch_attacks import prop_profile
        return prop_profile(animation_id) if animation_id is not None else None
    def article(slot,label,**extra):
        return dict(special=True,item_kind=-1,name=label,article_slot=slot,
                    asset_fighter_kind=kind,animation_id=0,**extra)
    if kind in (1,22) and name in ('SpecialNStart','SpecialNLoop','SpecialNEnd','SpecialAirNStart','SpecialAirNLoop','SpecialAirNEnd'):
        phase=0 if 'Start' in name else 1 if 'Loop' in name else 2
        return article(1,'Blaster',canonical_part=49,scale=.85,behavior='blaster',phase=name,
                       animation_id_override=phase+(3 if 'Air' in name else 0))
    if kind==7 and name in ('SpecialNEnd','SpecialAirNEnd'):
        return article(0,'Released needles',raw_joint=0,behavior='needle-release',phase=name,charged_preset=6)
    if kind==7 and name in ('SpecialNLoop','SpecialAirNLoop'):
        return article(1,'Needles',raw_joint=23,behavior='needles',phase=name,charged_preset=6)
    if kind==4 and name in ('SpecialHi1','SpecialHi2','SpecialHi3','SpecialHi4','SpecialAirHi1','SpecialAirHi2','SpecialAirHi3','SpecialAirHi4'):
        return dict(special=True,item_kind=-1,name='Final Cutter blade',source_archive='EfKbData.dat',
                    effect_table='effKirbyDataTable',effect_index=0,animation_id=0,raw_joint=44,
                    phase_offset=(0,23,58,60)[int(name[-1])-1],behavior='cutter',phase=name)
    if kind==4 and name in ('SpecialS','SpecialAirS'):
        return article(1,'Kirby hammer',raw_joint=44,behavior='hammer')
    if kind in (0,21) and name in ('SpecialS','SpecialSAir'):
        return article(2 if kind==0 else 3,'Cape' if kind==0 else 'Super Sheet',canonical_part=49,
                       animation_id_override=1 if 'Air' in name else 0,behavior='cape')
    if kind==9 and name in ('SpecialN','SpecialAirN','SpecialNHit','SpecialAirNHit'):
        return article(3,'Toad',raw_joint=109,behavior='toad',animation_id_override=1 if 'Hit' in name else 0)
    if kind==9 and name in ('SpecialHiStart','SpecialHiEnd','SpecialAirHiStart','SpecialAirHiEnd'):
        return article(2,'Peach parasol',raw_joint=109,behavior='peach-parasol',phase=name)
    if kind==8 and name.startswith('AttackS4'):
        return article(9,"Ness's bat",raw_joint=42,behavior='bat')
    if kind in (6,20) and name in ('SpecialNStart','SpecialNLoop','SpecialNEnd','SpecialAirNStart','SpecialAirNLoop','SpecialAirNEnd'):
        phase=0 if 'Start' in name else 1 if 'Loop' in name else 2
        return article(4,'Bow',canonical_part=49,behavior='bow',animation_id_override=phase+(3 if 'Air' in name else 0))
    if kind==20 and name in ('AppealR','AppealL'):
        # ftCl_AppealS_Anim spawns Article5 at FtPart_LThumbNb (31).
        return article(5,'Milk bottle',canonical_part=31,behavior='milk',phase=name)
    return None


def resolve_profile(files, report, specification):
    """Resolve the source archive/root without assuming table-root spelling."""
    if not specification or not specification.get('special'):
        return specification
    result=dict(specification)
    if 'asset_fighter_kind' in result:
        table=next(t for t in report['normal_tables'] if t['fighter_kind']==result['asset_fighter_kind'])
        result.update(source_archive=table['fighter_archive'],fighter_root=table['fighter_root'])
    if 'animation_id_override' in result:result['animation_id']=result.pop('animation_id_override')
    if result.get('behavior')=='needle-release':
        from pathlib import Path
        from .hsd import Archive
        ar=Archive((Path(files)/result['source_archive']).read_bytes())
        root=ar.public(result['fighter_root']);attrs=ar.pointer(root+4)
        item=ar.pointer(ar.pointer(root+72));special=ar.pointer(item+4)
        offset=8 if 'Air' in result['phase'] else 0
        result.update(spawn_offset=[ar.f32(attrs+offset),ar.f32(attrs+offset+4)],
                      projectile_speed=ar.f32(special+8),projectile_lifetime=ar.f32(special),
                      shot_ticks=[2,5,8,11,14,17],spread_policy='deterministic center of original random vertical spread')
    return result


def mapped_joint(files, kind, part):
    from pathlib import Path
    from .hsd import Archive, FormatError
    ar=Archive((Path(files)/'PlCo.dat').read_bytes())
    table=ar.pointer(ar.public('ftLoadCommonData')+16)
    row=ar.pointer(table+kind*4)
    joint=ar.u8(ar.pointer(row+4)+part)
    if joint==255:raise FormatError('Character prop attachment part is unavailable')
    return joint
