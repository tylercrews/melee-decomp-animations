"""Copy-rig and attachment regressions using synthetic poses, no game fixtures."""
import unittest
import numpy as np

from tools.melee_anim.kirby_powers import powers, validate_power, bone_slots, remap_tracks, attach_geometry
from tools.melee_anim.hsd import FormatError
from tools.melee_anim.motions import Track


class KirbyPowerTests(unittest.TestCase):
    def test_roster_choices_and_non_kirby_validation(self):
        choices=powers()
        self.assertEqual(choices[0],{'slug':'none','label':'None / Kirby'})
        self.assertEqual(len(choices),26)
        self.assertEqual(len({p['slug'] for p in choices}),26)
        self.assertEqual([p['label'] for p in choices[1:]],sorted([p['label'] for p in choices[1:]],key=str.casefold))
        self.assertIn('zelda',[p['slug'] for p in choices])
        self.assertIn('sheik',[p['slug'] for p in choices])
        self.assertEqual(validate_power('fox','none'),'none')
        for character,power in [('fox','mario'),('kirby','../mario'),('kirby','nana')]:
            with self.assertRaises(ValueError):validate_power(character,power)

    def test_reserved_slot_mapping_preserves_body_pose_across_inserted_bones(self):
        # Reserved part IDs from the source layout; remaining fields are unused
        # by this mapping fixture, not an extracted binary asset.
        parts=[[i,0,0,0] for i in (7,8,9,10,28,29,30,31,32,33,34,15,16)]
        track=Track(23,1,0,0,0,b'synthetic retained stream')
        for count,mask,index in [(46,0,23),(50,0xF,27),(53,0x7F0,30),(48,0x1800,25)]:
            slots=bone_slots(count,parts,mask)
            self.assertEqual(len(slots),count)
            mapped=remap_tracks([track],46,count,parts,mask)[0]
            self.assertEqual(mapped.joint_index,index)
            self.assertEqual(mapped.data,track.data)
            self.assertEqual(remap_tracks([mapped],count,46,parts)[0],track)
        self.assertEqual(remap_tracks([Track(7,2,0,0,0,b'')],50,46,parts),[])
        with self.assertRaises(FormatError):remap_tracks([],49,46,parts)

    def test_hat_root_is_replaced_by_head_world_matrix_and_normals_stay_unit(self):
        root=np.eye(4);root[:3,3]=[10,20,30]
        head=np.eye(4);head[:3,:3]=np.diag([2.,3.,4.]);head[:3,3]=[-5,2,8]
        positions=np.array([[10.,21.,30.]])
        normals=np.array([[0.,1.,0.]])
        p,n=attach_geometry([(positions,normals)],head,root)[0]
        np.testing.assert_allclose(p,[[-5.,5.,8.]])
        np.testing.assert_allclose(n,[[0.,1.,0.]])
        np.testing.assert_array_equal(root[:3,3],[10,20,30])


if __name__=='__main__':unittest.main()
