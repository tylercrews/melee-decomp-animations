import math
import unittest

import numpy as np

from tools.melee_anim.preview import camera_basis, joint_visibility, pose_matrices, render_frame, srt_matrix, texture_uv
from tools.melee_anim.motions import Track
import struct


class PreviewTests(unittest.TestCase):
    def test_zero_and_small_negative_scale_follow_hsd_clamp(self):
        bone = {"index": 0, "parent": None, "flags": 8, "rotation": [0, 0, 0],
                "position": [0, 0, 0], "scale": [1, 1, 1]}
        for value, expected in [(0, .001), (-.0001, .001), (-.01, -.01)]:
            track = Track(0, 8, 0, 0, 0, b"\x11"+struct.pack("<f", value)+b"\x01"+struct.pack("<f", value))
            self.assertAlmostEqual(pose_matrices([bone], [track], 0)[0, 0, 0], expected)

    def test_node_visibility_does_not_hide_children_and_branch_can_be_overridden(self):
        bones = [{"parent": None, "flags": 0}, {"parent": 0, "flags": 0},
                 {"parent": 1, "flags": 16}, {"parent": 0, "flags": 0}]
        def track(node, channel, value):
            return Track(node, channel, 0, 0, 0, b"\x11"+struct.pack("<f", value)+b"\x01"+struct.pack("<f", value))
        self.assertEqual(joint_visibility(bones, [track(1, 11, .5)], 0), [True, False, False, True])
        self.assertEqual(joint_visibility(bones, [track(1, 12, 0), track(2, 11, 1)], 0), [True, False, True, True])
        self.assertEqual(joint_visibility(bones, [track(1, 12, 1)], 0), [True]*4)

    def test_local_matrix_rotation_translation_and_scale(self):
        matrix = srt_matrix([0, 0, math.pi/2], [2, 1, 1], [3, 4, 5])
        np.testing.assert_allclose(matrix @ [1, 0, 0, 1], [3, 6, 5, 1], atol=1e-12)

    def test_missing_pose_channels_retain_defaults_and_parent_transform(self):
        bones = [{"index": 0, "parent": None, "flags": 8, "rotation": [0, 0, 0],
                  "position": [3, 0, 0], "scale": [1, 1, 1]},
                 {"index": 1, "parent": 0, "flags": 8, "rotation": [0, 0, 0],
                  "position": [0, 2, 0], "scale": [1, 1, 1]}]
        track = Track(1, 6, 0, 0, 0, b"\x11"+struct.pack("<f", 4)+b"\x01"+struct.pack("<f", 4))
        world = pose_matrices(bones, [track], 0)
        np.testing.assert_allclose(world[1, :3, 3], [3, 4, 0])

    def test_depth_buffer_keeps_front_triangle(self):
        mesh = {"material_index": 0, "uvs": [[0, 0]]*3, "triangles": [[0, 1, 2]]}
        model = {"meshes": [mesh, {**mesh, "material_index": 1}],
                 "materials": [{"textures": [], "diffuse_rgba": [255, 0, 0, 255]},
                               {"textures": [], "diffuse_rgba": [0, 0, 255, 255]}]}
        p = np.array([[-1, -1, 1], [1, -1, 1], [0, 1, 1]], dtype=float)
        n = np.tile([0., 0., 1.], (3, 1))
        image = render_frame(model, [(p, n), (p-[0, 0, 1], n)], {},
                             camera_basis(0), 16, 16, np.zeros(3), 6, (0, 0, 0, 255))
        color = np.asarray(image)[8, 8]
        self.assertGreater(color[0], 200)
        self.assertEqual(color[2], 0)

    def test_gx_mirror_wrap_and_texture_repeat_matrix(self):
        uv = np.array([[.1, .5], [.6, .5], [-.1, .5]])
        desc = {"texture_matrix": np.diag([2, 1, 1, 1]).tolist(), "wrap_s": 2, "wrap_t": 0}
        transformed = texture_uv(uv, desc)
        np.testing.assert_allclose(transformed[:, 0], [.2, .8, .2])
        np.testing.assert_allclose(transformed[:, 1], [.5]*3)


if __name__ == "__main__":
    unittest.main()
