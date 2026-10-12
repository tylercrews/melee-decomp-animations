import struct
import unittest
import numpy as np
from tools.melee_anim.game_watch_attacks import prop_profile,visibility_timeline
from tools.melee_anim.electric_burst import is_judge9,particle_program


class GameWatchAttackTests(unittest.TestCase):
    def test_distinct_source_articles_and_attachment_slots(self):
        for aid,slot,joint in [(46,0,32),(62,2,32),(70,4,17),(68,3,1),(71,5,21),(319,7,0)]:
            p=prop_profile(aid);self.assertEqual((p['article_slot'],p['raw_joint']),(slot,joint))
        self.assertIsNone(prop_profile(69),'forward air uses timed fighter parts, not a guessed article')
        self.assertEqual([prop_profile(a)['animation_id'] for a in (46,49,50,51)],[0,1,2,3])

    def test_judgment_numbers_ignore_duplicate_packed_names(self):
        for base in (297,306):
            for number in range(1,10):
                p=prop_profile(base+number-1)
                self.assertEqual(p['judge_number'],number);self.assertEqual(p['frozen_frame'],number)
                self.assertEqual(p['spawn_variable'],1);self.assertEqual(p['canonical_part'],49)
        self.assertTrue(is_judge9('game-and-watch','attack-305_source'))
        self.assertTrue(is_judge9('game-and-watch','attack-314_source'))
        self.assertFalse(is_judge9('mario','attack-305_source'))
        self.assertFalse(is_judge9('game-and-watch','attack-304_source'))

    def test_bucket_callback_and_authored_hide_timing(self):
        model={'visibility':{'defaults':[0]+[-1]*10}}
        commands=[{'offset':0,'opcode':2,'first_word':'0x08000005','timer_ticks':5},
                  {'offset':4,'opcode':19,'first_word':'0x4c000001','command_variable':{'index':0,'value':1}},
                  {'offset':8,'opcode':2,'first_word':'0x08000026','timer_ticks':38},
                  {'offset':12,'opcode':31,'first_word':'0x7c000000','visibility_group':5,'visibility_value':-1},
                  {'offset':16,'opcode':0,'first_word':'0x00000000'}]
        m={'frames':40,'script':{'commands':commands}}
        timeline=visibility_timeline(model,m,317)
        self.assertEqual(timeline[0][1][5],-1)
        self.assertEqual(next(s for t,s in timeline if t==5)[5],2)
        self.assertEqual(timeline[-1][1][5],-1)
        empty={'frames':40,'script':{}}
        self.assertEqual(visibility_timeline(model,empty,318)[0][1][5:9],[2,0,-1,-1])
        self.assertEqual(visibility_timeline(model,empty,319)[0][1][5:9],[2,-1,-1,-1])

    def test_original_particle_random_size_and_texture_loop_are_deterministic(self):
        program=b'\xac\x00'+struct.pack('>2f',2.,3.)+b'\xfa\x03\xbc\x00\x08\x01\xfb\xff'
        args=(program,8,0.,[0,0,0])
        a=particle_program(*args,np.random.default_rng(12));b=particle_program(*args,np.random.default_rng(12))
        self.assertEqual(len(a),3)
        self.assertTrue(2<=a[0][0]<5)
        for x,y in zip(a,b):
            self.assertEqual(x[:2],y[:2]);np.testing.assert_array_equal(x[2],y[2])
        with self.assertRaises(ValueError):particle_program(b'\xee',1,1.,[0,0,0],np.random.default_rng(12))


if __name__=='__main__':unittest.main()
