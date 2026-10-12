"""Synthetic particle timing, source spawn decoding and card geometry."""
import struct
import unittest
import numpy as np
from tools.melee_anim.hsd import Archive,FormatError
from tools.melee_anim.inspect_motions import script_summary
from tools.melee_anim.sleep_bubbles import bubble_spawns,particle_samples,SleepBubbles
from tools.melee_anim.tests.test_motions import dat


class SleepBubbleTests(unittest.TestCase):
    def test_source_spawn_fields_and_wait_timing(self):
        raw=struct.pack('>II3h3HI',(10<<26)|(19<<18),416<<16,0,400,1200,0,0,0,0)
        script=script_summary(Archive(dat(raw)),0,bytes([5]))
        motion={'frames':120,'script':script}
        spawn=bubble_spawns(motion)[0]
        self.assertEqual(spawn[0],0)
        self.assertEqual(spawn[1]['raw_joint'],19)
        self.assertEqual(spawn[1]['offset'],[0,1.5625,4.6875])
        self.assertFalse(spawn[1]['common_joint'])
        script['commands'].insert(0,dict(offset=-4,opcode=1,first_word='0x0400004d',timer_ticks=77))
        self.assertEqual(bubble_spawns(motion)[0][0],77)
        script['commands'][1]['gfx_spawn']['gfx_id']=415
        self.assertEqual(bubble_spawns(motion),[])

    def test_size_growth_and_alpha_fade_follow_game_ticks(self):
        program=b'\xa0\x00'+struct.pack('>f',1)+b'\xa0\x04'+struct.pack('>f',5)+b'\xc8\x04\x00\x05\xff'
        samples=particle_samples(program,10,9)
        np.testing.assert_allclose([s[0] for s in samples],[1,2,3,4,5])
        np.testing.assert_allclose([s[2][3] for s in samples],[255,191.25,127.5,63.75,0])
        for raw in (b'\xa0',b'\xa0\x00\x3f',b'\x90'):
            with self.assertRaises(FormatError):particle_samples(raw,1,1)

    def test_snapshot_origin_lifetime_fractional_size_and_camera_facing(self):
        effect=SleepBubbles.__new__(SleepBubbles)
        effect.spawns=[(-2,np.array([3.,4.,5.]),0.)]
        effect.samples=[(s,0,np.ones(4)*255,np.zeros(4)) for s in (1.,2.,3.,4.)]
        effect.speed=.2;effect.radius=1.;effect.angle=0.;effect.gravity=0.
        corners,_,_=next(effect.active(.5,np.eye(3)))
        np.testing.assert_allclose((corners[1]-corners[0]),[7,0,0])
        np.testing.assert_allclose(corners.mean(0),[4,4.7,5])
        self.assertEqual(list(effect.active(2,np.eye(3))),[])
        view=np.array([[0,0,1],[0,1,0],[-1,0,0]])
        corners,_,_=next(effect.active(0,view))
        self.assertAlmostEqual(np.ptp((corners@view)[:,2]),0)


if __name__=='__main__':unittest.main()
