"""Synthetic movement/trajectory checks; original game data stays out of tests."""
import unittest
import numpy as np
from tools.melee_anim.movement import movement_label, flight_heights, JumpScene, jump_duration, centered_jump_setting
from tools.melee_anim.preview import projected_pose_center, camera_basis, fit_knockdown_camera


class MovementTests(unittest.TestCase):
    def test_centered_camera_follows_translation_without_zooming_or_hidden_geometry(self):
        shape=np.array([[-2.,1.,3.],[3.,0.,-1.],[1.,5.,2.]])
        view=camera_basis(35,20,15)
        centered=[]
        for height in (0,10,30,7):
            pose=[(shape+[0,height,0],None),(shape+1000,None)]
            pivot=projected_pose_center(pose,[True,False],view)
            projected=(pose[0][0]-pivot)@view
            np.testing.assert_allclose((projected.min(0)+projected.max(0))[:2],0,atol=1e-12)
            centered.append(pose[0][0]-pivot)
        _,scale=fit_knockdown_camera(np.concatenate(centered),view,256)
        for shape in centered:
            self.assertLessEqual(np.abs(shape@view)[:,:2].max()*scale,256*.41+1e-10)
        np.testing.assert_allclose(centered[0],centered[2],atol=1e-12)
        self.assertTrue(centered_jump_setting('movement-fullhop_source','on'))
        self.assertFalse(centered_jump_setting('taunt_source','off'))
        for action,value in (('movement-2_source','on'),('tech-199_source','on'),('movement-shorthop_source','bad')):
            with self.assertRaises(ValueError):centered_jump_setting(action,value)

    def test_standing_idle_and_locomotion_are_distinct_from_held_item_stances(self):
        self.assertEqual(movement_label(2,'Wait1'),'Standing')
        self.assertEqual(movement_label(3,'Wait2'),'Idle 1')
        self.assertEqual(movement_label(4,'Wait3'),'Idle 2')
        self.assertIsNone(movement_label(6,'WaitItem'))
        self.assertIsNone(movement_label(4,'AttackDash'))
        self.assertEqual(movement_label(12,'Dash'),'Dashing')
        self.assertEqual(movement_label(13,'Run'),'Running')

    def test_gravity_grace_tick_terminal_speed_and_shorter_hop(self):
        full=flight_heights(2,.5,1)
        self.assertEqual(full,[0,2,3.5,4.5,5,5,4.5,3.5,2.5,1.5,.5,0])
        short=flight_heights(1,.5,1)
        self.assertLess(max(short),max(full));self.assertLess(len(short),len(full))
        self.assertEqual(short[-1],0)
        for args in ((0,.5,1),(1,0,1),(1,.5,float('nan'))):
            with self.assertRaises(ValueError):flight_heights(*args)

    def test_phase_boundaries_fall_loop_and_fractional_height(self):
        scene=JumpScene.__new__(JumpScene)
        scene.startup=2;scene.heights=flight_heights(2,.5,1);scene.flight=len(scene.heights)-1
        scene.phases={k:({'frames':n,'phase':k},[]) for k,n in {'squat':10,'jump':4,'fall':2,'landing':3,'standing':20}.items()}
        scene.duration=scene.startup+scene.flight+3
        self.assertEqual(scene.sample(1)[0]['phase'],'squat')
        self.assertEqual(scene.sample(2)[0]['phase'],'jump')
        self.assertEqual(scene.sample(3)[3],2)
        self.assertEqual(scene.sample(6)[0]['phase'],'fall')
        self.assertEqual(scene.sample(7.5)[2],1.5)
        self.assertEqual(scene.sample(7.5)[3],4.75)
        self.assertEqual(scene.sample(13)[0]['phase'],'landing')
        self.assertEqual(scene.sample(scene.duration)[0]['phase'],'standing')
        parameters={'startup':2,'full_velocity':2,'short_velocity':1,'gravity':.5,'terminal_velocity':1}
        self.assertEqual(jump_duration(parameters,'fullhop',3),scene.duration)


if __name__=='__main__':unittest.main()
