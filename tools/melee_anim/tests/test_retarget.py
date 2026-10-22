"""Borrowed wireframe poses: synthetic rigs only, no game fixtures."""
import math
import unittest

import numpy as np

from tools.melee_anim.batch_exports import family
from tools.melee_anim.export_model import local_matrix, world_matrices
from tools.melee_anim.preview import pose_matrices
from tools.melee_anim.retarget import PoseRetarget, correspondence, euler, identical_skeleton, rotation


class Curve:
    def __init__(self, joint, channel, function):
        self.joint_index, self.channel, self.function = joint, channel, function

    def evaluate(self, frame):
        return self.function(frame)


def rig(kind, specs):
    """specs: (parent, position, rotation); flag 8 matches type-1 FigaTrees."""
    bones = [{'index':i, 'parent':p, 'flags':8, 'position':list(pos), 'rotation':list(rot), 'scale':[1,1,1]}
             for i,(p,pos,rot) in enumerate(specs)]
    for bone, matrix in zip(bones, world_matrices(bones)):
        bone['world_bind_matrix'] = np.asarray(matrix).tolist()
    return {'fighter_kind':kind, 'bones':bones}


class Parts:
    """Stand-in for PlCo's tables: game remap plus hip and root joints."""
    def __init__(self, remap, hips, roots=(0,1)):
        self.mapping, self.hips, self.roots = remap, hips, roots

    def remap(self, source_kind, target_kind, count):
        return dict(self.mapping)

    def hip_height(self, model):
        return self.hips[model['fighter_kind']]

    def joint(self, kind, part):
        return self.roots[part] if part < len(self.roots) else None


class RetargetTests(unittest.TestCase):
    def test_euler_inverts_hsd_rotation_order(self):
        for angles in ([.3,-.7,1.1],[-2.5,.2,-.4],[0,math.pi/2,0]):
            matrix = local_matrix(angles,[1,1,1],[0,0,0])[:3,:3]
            np.testing.assert_allclose(local_matrix(euler(matrix),[1,1,1],[0,0,0])[:3,:3], matrix, atol=1e-9)

    def test_world_rotations_follow_source_despite_a_pose_bind_and_proportions(self):
        # Source arm rests 40 degrees lower and is shorter, with an unmapped
        # intermediate joint whose rotation the game's local copy would lose.
        source = rig(1, [(None,[0,0,0],[0,0,0]), (0,[0,8,0],[0,0,0]), (1,[1,2,0],[0,0,-.7]),
                         (2,[0,0,0],[0,0,.3]), (3,[2,0,0],[0,0,0])])
        target = rig(2, [(None,[0,0,0],[0,0,0]), (0,[0,12,0],[0,0,0]), (1,[1.5,3,0],[0,0,0]), (2,[4,0,0],[0,0,0])])
        parts = Parts({0:0, 1:1, 2:2, 3:4}, {1:8., 2:12.})
        tracks = [Curve(1,5,lambda t:.5*t), Curve(1,6,lambda t:8-.25*t), Curve(1,2,lambda t:.2*t),
                  Curve(2,3,lambda t:-.7+.4*t), Curve(3,1,lambda t:.3*t), Curve(4,3,lambda t:-.5*t)]
        solver = PoseRetarget(parts, source, target, tracks, 1)
        for frame in (0., 1., 2.5):
            src = pose_matrices(source['bones'], tracks, frame)
            out = pose_matrices(target['bones'], solver.tracks(), frame)
            for t,s in solver.mapping.items():
                np.testing.assert_allclose(rotation(out[t]), rotation(src[s]), atol=1e-9)
            # Root motion is the source delta from bind, scaled by hip height.
            np.testing.assert_allclose(out[1][:3,3], [.75*frame,12-.375*frame,0], atol=1e-9)

    def test_unmapped_chain_is_filled_from_its_base_not_by_nearest_child(self):
        # Ganondorf-like head: the tip would steal the head joint if matched first.
        source = rig(1, [(None,[0,0,0],[0,0,0]), (0,[0,10,0],[0,0,0]), (1,[0,2.8,-.2],[0,0,0]),
                         (1,[0,3.5,.3],[0,0,0]), (3,[0,0,0],[0,0,0]), (4,[0,.8,.5],[0,0,0])])
        target = rig(2, [(None,[0,0,0],[0,0,0]), (0,[0,10,0],[0,0,0]), (1,[0,2.8,-.2],[0,0,0]),
                         (1,[0,3.1,-.1],[0,0,0]), (3,[0,.7,.2],[0,0,0])])
        mapping, filled = correspondence(Parts({0:0, 1:1}, {1:10., 2:10.}), source, target)
        self.assertEqual(filled, {2:2, 3:3, 4:5})
        self.assertEqual(mapping[1], 1)

    def test_identical_skeleton_and_batch_family(self):
        a = rig(1, [(None,[0,0,0],[0,0,0]), (0,[0,1,0],[0,0,.2])])
        b = rig(2, [(None,[0,0,0],[0,0,0]), (0,[0,1,0],[0,0,.2])])
        c = rig(3, [(None,[0,0,0],[0,0,0]), (0,[0,1.5,0],[0,0,.2])])
        self.assertTrue(identical_skeleton(a,b));self.assertFalse(identical_skeleton(a,c))
        self.assertEqual(family({'key':'other-ganondorf-victory1_source','animation_type':'victory',
                                 'label':'Ganondorf — Victory 1'}),('victory','victory poses'))
        self.assertEqual(family({'key':'other-sheik-results-clap_source','animation_type':'clapping',
                                 'label':'Sheik — Clapping'}),('clapping','clapping'))


if __name__ == '__main__':
    unittest.main()
