"""Synthetic source timing/coverage/attachment checks without game fixtures."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import numpy as np
from PIL import Image

from tools.melee_anim.character_effects import (character_effects,effect_archives,
    animation_time,shared_loop_period,TimedTrack,effect_pixels,composite_effect,CharacterEffects)


class CharacterEffectTests(unittest.TestCase):
    def test_reflector_variants_use_shared_archive_and_raw_hip(self):
        for kind in (1,22):
            for air in ('','Air'):
                for phase,index in [('Start',1),('Loop',0),('Hit',2)]:
                    spec=character_effects(kind,'Special'+air+'Lw'+phase)[0]
                    self.assertEqual((spec['descriptor_id'],spec['gfx_id'],spec['raw_joint']),(index,1160+index,4))
                    self.assertEqual(spec['source_archive'],'EfFxData.dat')
                self.assertEqual(character_effects(kind,'Special'+air+'LwEnd'),[])

    def test_other_source_profiles_and_no_unrelated_substitutions(self):
        self.assertEqual(character_effects(8,'SpecialLwHold')[0]['descriptor_id'],2)
        self.assertEqual(character_effects(8,'SpecialAirLwHold')[0]['raw_joint'],23)
        self.assertEqual(character_effects(0,'SpecialLw')[0]['source_archive'],'EfMrData.dat')
        self.assertEqual(character_effects(21,'SpecialLw')[0]['source_archive'],'EfMrData.dat')
        self.assertEqual(character_effects(17,'SpecialLw')[0]['source_archive'],'EfLgData.dat')
        for kind,name in [(1,'SpecialNLoop'),(4,'SpecialLw'),(8,'SpecialLwStart'),(8,'SpecialLwEnd'),(22,'AttackS4')]:
            self.assertEqual(character_effects(kind,name),[])

    def test_per_aobj_looping_clamping_and_original_track_identity(self):
        track=SimpleNamespace(channel=8,joint_index=1,evaluate=lambda t:t*2)
        wrapped=TimedTrack(track,(6,True));held=TimedTrack(track,(6,False))
        self.assertEqual((wrapped.channel,wrapped.joint_index),(8,1))
        self.assertEqual(wrapped.evaluate(6),0)
        self.assertEqual(wrapped.evaluate(8),4)
        self.assertEqual(held.evaluate(8),12)
        self.assertEqual(animation_time(12,0,False),12)

    def test_shared_fighter_effect_loop_keeps_both_authored_rates(self):
        self.assertEqual(shared_loop_period(28,character_effects(1,'SpecialLwLoop')),84)
        self.assertEqual(shared_loop_period(20,character_effects(8,'SpecialLwHold')),40)
        with self.assertRaises(ValueError):shared_loop_period(0,[])

    def test_color_generator_and_blend_override_material_zero_alpha(self):
        pixels=np.array([[[0,0,0,128],[255,255,255,255]]],dtype='uint8')
        tev=bytearray(32);tev[20:23]=bytes([0,0,255]);tev[16:19]=bytes([0,204,255]);tev[28:32]=(1<<30).to_bytes(4,'big')
        result=effect_pixels(pixels,{'tev_bytes':bytes(tev)},1,[0,0,0],0)
        np.testing.assert_array_equal(result,[[[0,0,255,128],[0,204,255,255]]])
        blank=effect_pixels(pixels,{},0,[255,0,0],0)
        self.assertTrue(np.all(blank[:,:,3]==0))

    def test_additive_light_preserves_fighter_and_transparent_coverage(self):
        red=Image.new('RGBA',(1,1),(255,0,0,255));blue=Image.new('RGBA',(1,1),(0,0,255,128))
        self.assertEqual(composite_effect(red,blue,True).getpixel((0,0)),(255,0,128,255))
        clear=Image.new('RGBA',(1,1),(100,50,80,0))
        self.assertEqual(composite_effect(clear,blue,True).getpixel((0,0)),(0,0,255,128))
        black=Image.new('RGBA',(1,1),(0,0,0,128))
        self.assertEqual(composite_effect(clear,black,True).getpixel((0,0)),(0,0,0,128))

    def test_attachment_uses_root_y_scale_and_phase_local_effect_time(self):
        group=object.__new__(CharacterEffects)
        group.scene=SimpleNamespace(sample=lambda t:(None,None,None,1,t-4))
        a,b=Mock(),Mock();group.entries=[(0,4,a),(1,4,b)]
        matrices=np.tile(np.eye(4),(5,1,1));matrices[0][1,1]=3
        matrices[4][:3,:3]*=90;matrices[4][:3,3]=[2,7,0]
        active=group.active(10,matrices)
        self.assertEqual(len(active),1);self.assertIs(active[0][0],b)
        self.assertEqual(active[0][1],6);self.assertEqual(active[0][2][1],3)
        np.testing.assert_array_equal(active[0][2][0],[2,7,0])

    def test_fingerprints_include_effects_in_later_sequence_phases(self):
        actor={'character_effects':[],'sequence':{'phases':[{'character_effects':None},{'character_effects':character_effects(1,'SpecialLwLoop')}]}}
        self.assertEqual(effect_archives(actor),{'EfFxData.dat'})


if __name__=='__main__':unittest.main()
