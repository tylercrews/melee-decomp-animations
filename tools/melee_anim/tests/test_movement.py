"""Synthetic movement/trajectory checks; original game data stays out of tests."""
import unittest
from tools.melee_anim.movement import movement_label, flight_heights, JumpScene, jump_duration


class MovementTests(unittest.TestCase):
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
