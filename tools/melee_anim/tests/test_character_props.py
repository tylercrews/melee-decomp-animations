import unittest
from tools.melee_anim.character_props import character_prop, resolve_profile


class CharacterPropTests(unittest.TestCase):
    def test_released_needles_use_fixed_spawn_pose_source_speed_and_lifetime(self):
        import numpy as np
        from tools.melee_anim.held_items import HeldItem
        item=object.__new__(HeldItem)
        item.specification=dict(behavior='needle-release',shot_ticks=[2,5,8,11,14,17],phase='SpecialNEnd',
                                projectile_speed=4.,projectile_lifetime=30.,spawn_offset=[8.,8.])
        item.bones=[dict(index=0,parent=None,flags=0,rotation=[0,0,0],scale=[1,1,1],position=[0,0,0])]
        mesh=dict(source_positions=[[0,0,0]],source_normals=[[0,0,1]],palette_indices=[0],
                  envelopes=[[dict(joint_index=0,weight=1.)]],owner_joint_index=0)
        item.model=dict(meshes=[mesh]*6)
        def origin(tick):
            result=np.eye(4);result[0,3]=tick;return result
        item.anchor_at=origin
        geometry,visible=item.pose(np.eye(4),10)
        self.assertEqual(visible,[True,True,True,False,False,False])
        np.testing.assert_allclose(geometry[0][0],[[42,8,0]])
        np.testing.assert_allclose(geometry[1][0],[[33,8,0]])
        self.assertFalse(item.pose(np.eye(4),35)[1][0])

    def test_requested_props_use_separate_character_articles_or_effect_mesh(self):
        fox=character_prop(1,'SpecialNLoop');falco=character_prop(22,'SpecialAirNLoop')
        self.assertEqual(fox['article_slot'],1);self.assertEqual(falco['article_slot'],1)
        self.assertEqual(fox['canonical_part'],49);self.assertEqual(fox['scale'],.85)
        sheik=character_prop(7,'SpecialNLoop')
        self.assertEqual(sheik['raw_joint'],23);self.assertEqual(sheik['charged_preset'],6)
        release=character_prop(7,'SpecialNEnd')
        self.assertEqual(release['article_slot'],0);self.assertEqual(release['behavior'],'needle-release')
        cutter=character_prop(4,'SpecialAirHi3')
        self.assertEqual(cutter['effect_index'],0);self.assertEqual(cutter['raw_joint'],44)
        self.assertEqual(cutter['phase_offset'],58)

    def test_unrelated_actions_never_get_substituted_props(self):
        for kind,name in [(0,'SpecialN'),(1,'SpecialHi'),(7,'SpecialNStart'),(4,'SpecialN'),(27,'SpecialNLoop')]:
            self.assertIsNone(character_prop(kind,name))

    def test_additional_profiles_keep_correct_slots_and_animation_variants(self):
        self.assertEqual(character_prop(0,'SpecialS')['article_slot'],2)
        self.assertEqual(character_prop(21,'SpecialS')['article_slot'],3)
        self.assertEqual(character_prop(9,'SpecialN')['raw_joint'],109)
        self.assertEqual(character_prop(8,'AttackS4')['raw_joint'],42)
        self.assertEqual(character_prop(4,'SpecialAirS')['animation_id'],0)
        self.assertEqual(character_prop(20,'SpecialAirNEnd')['animation_id_override'],5)

    def test_root_spelling_and_archive_are_resolved_from_verified_report(self):
        report={'normal_tables':[dict(fighter_kind=22,fighter_archive='original.dat',fighter_root='originalRoot')]}
        prop=resolve_profile(None,report,character_prop(22,'SpecialNEnd'))
        self.assertEqual(prop['source_archive'],'original.dat');self.assertEqual(prop['fighter_root'],'originalRoot')

    def test_kirby_runtime_parts_include_reserved_holes_in_base_and_power_rigs(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from pathlib import Path
        from tools.melee_anim.held_items import hold_joint
        # Synthetic reserved slots; runtime hand slot 6 is mesh bone 4.
        archive=SimpleNamespace(pointer=lambda _:0,public=lambda _:0,u8=lambda _:6)
        table=dict(fighter_archive='synthetic.dat',fighter_root='synthetic')
        with patch.object(Path,'read_bytes',return_value=b''),patch('tools.melee_anim.held_items.Archive',return_value=archive),patch('tools.melee_anim.kirby_powers.reserved_parts',return_value=[[2],[3]]):
            self.assertEqual(hold_joint(Path('.'),table,dict(fighter_kind=4,bones=[{}]*7),Path('.')),4)
            self.assertEqual(hold_joint(Path('.'),table,dict(fighter_kind=4,bones=[{}]*8,kirby_part_mask=1),Path('.')),5)
