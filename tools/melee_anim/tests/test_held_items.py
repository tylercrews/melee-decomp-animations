"""Source-layout/timing/attachment checks without original game assets."""
import unittest
import numpy as np
from tools.melee_anim.held_items import billboard_matrix, constrained_transform, item_for_motion, script_events, texture_color_generator


class HeldItemTests(unittest.TestCase):
    def test_item_glow_uses_original_color_constants_and_preserves_intensity_alpha(self):
        tev=bytearray(32);tev[8:12]=bytes([133,128,8,15]);tev[16:19]=bytes([255,255,153]);tev[20:23]=bytes([255,255,153]);tev[28:32]=(0xC0000077).to_bytes(4,'big')
        pixels=np.array([[[0,0,0,0],[128,128,128,128],[255,255,255,255]]],dtype='uint8')
        result=texture_color_generator(pixels,tev)
        np.testing.assert_array_equal(result[:,:,:3],[[[255,255,153]]*3])
        np.testing.assert_array_equal(result[:,:,3],pixels[:,:,3])
        tev[28:32]=bytes(4)
        np.testing.assert_array_equal(texture_color_generator(pixels,tev),pixels)

    def test_star_glow_faces_camera_without_moving_or_resizing(self):
        from tools.melee_anim.preview import camera_basis
        original=np.diag([2.,3.,4.,1.]);original[:3,3]=[5,6,7]
        view=camera_basis(65,20,10)
        result=billboard_matrix(original,view)
        np.testing.assert_allclose(result[:3,3],[5,6,7])
        np.testing.assert_allclose(np.linalg.norm(result[:3,:3],axis=0),[2,3,4])
        np.testing.assert_allclose(result[:3,2]/4,view[:,2])

    def test_item_aobj_retains_authored_scaling_flags_without_figatree_override(self):
        import struct
        from tools.melee_anim.preview import pose_matrices
        from tools.melee_anim.motions import Track
        from tools.melee_anim.export_model import world_matrices
        bones=[dict(index=0,parent=None,flags=0,rotation=[0,0,0],position=[0,0,0],scale=[2,3,4]),
               dict(index=1,parent=0,flags=8,rotation=[0,0,0],position=[1,1,1],scale=[1,1,1])]
        track=Track(1,8,0,0,0,b'\x11'+struct.pack('<f',1)+b'\x01'+struct.pack('<f',1))
        np.testing.assert_allclose(pose_matrices(bones,[track],0,tree_type=None),world_matrices(bones))

    def test_reused_swing_names_are_identified_by_submotion_id(self):
        self.assertEqual([item_for_motion('attack-'+str(a),0)['name'] for a in (108,112,116,120,124,128)],
                         ['Beam Sword','Home-Run Bat','Parasol','Fan','Star Rod',"Lip's Stick"])
        self.assertEqual(item_for_motion('attack-123',24)['variant'],3)
        self.assertEqual(item_for_motion('attack-296',2)['name'],'Home-Run Bat')
        self.assertEqual(item_for_motion('attack-296',2)['variant'],4)
        self.assertIsNone(item_for_motion('attack-296',0))
        for action,kind in [('victory1',0),('attack-108',27),('attack-108',28),('attack-108',32),('attack-79',0)]:
            self.assertIsNone(item_for_motion(action,kind))

    def test_constraint_uses_target_position_and_rotation_but_keeps_item_scale(self):
        anchor=np.diag([2.,3.,4.,1.]);anchor[:3,3]=[5,6,7]
        target=np.array([[0.,-8,0,20],[9.,0,0,30],[0,0,10,40],[0,0,0,1]])
        result=constrained_transform(target,anchor)@anchor
        np.testing.assert_allclose(result[:3,3],target[:3,3])
        np.testing.assert_allclose(result[:3,:3],[[0,-3,0],[2,0,0],[0,0,4]])

    def test_item_timing_follows_wait_call_return_and_relative_wait(self):
        def cmd(offset,op,value=0,**kw):
            return dict(offset=offset,opcode=op,first_word=hex((op<<26)|value),**kw)
        script={'commands':[cmd(0,2,5,timer_ticks=5),cmd(4,5,target=40),cmd(12,1,3,timer_ticks=3),cmd(16,42),cmd(20,0)],
                'reachable_blocks':[{'commands':[cmd(40,19,command_variable={'index':0,'value':1}),cmd(44,6)]}]}
        self.assertEqual([(t,c['opcode']) for t,c in script_events(script,20)],[(5,19),(8,42)])

    def test_item_timing_loop_is_bounded_by_source_interval(self):
        script={'commands':[{'offset':0,'opcode':42,'first_word':hex(42<<26)},
                            {'offset':4,'opcode':1,'first_word':hex((1<<26)|2),'timer_ticks':2},
                            {'offset':8,'opcode':7,'first_word':hex(7<<26),'target':0}]}
        self.assertEqual([t for t,_ in script_events(script,5)],[0,2,4])
