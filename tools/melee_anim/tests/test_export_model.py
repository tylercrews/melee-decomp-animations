import math
import unittest

import numpy as np

from tools.melee_anim.export_model import local_matrix, palette_matrices, primary_drawables, skin_source_mesh, texture_matrix


class SkinningTests(unittest.TestCase):
    def test_visibility_class_two_uses_an_independent_drawable_list(self):
        classes = [{"groups": [[[0], [1]]]}, {"groups": [[[2]]]},
                   {"groups": [[[3]]]}, {"groups": [[[4]]]}]
        # Class 2 index 3 must remain; class 4 item-only index 5 is hidden.
        self.assertEqual(primary_drawables(7, classes, [[[0, 5]]]), {0, 1, 3, 6})

    def test_texture_repeat_and_mirror_offset(self):
        texture = {"scale": [1, 1, 1], "rotation": [0, 0, 0],
                   "translation": [0, 0, 0], "repeat_s": 2, "repeat_t": 1, "wrap_t": 0}
        np.testing.assert_allclose(texture_matrix(texture) @ [.25, .75, 1, 1], [.5, .75, 1, 1])
        texture["wrap_t"] = 2
        np.testing.assert_allclose(texture_matrix(texture) @ [.25, .75, 1, 1], [.5, -.25, 1, 1])

    def test_euler_rotation_convention(self):
        m = local_matrix([0, 0, math.pi / 2], [1, 1, 1], [0, 0, 0])
        np.testing.assert_allclose(m @ [1, 0, 0, 1], [0, 1, 0, 1], atol=1e-12)

    def test_single_bone_local_positions_and_mixed_bind_positions(self):
        inverse0 = [1, 0, 0, -10, 0, 1, 0, 0, 0, 0, 1, 0]
        inverse1 = [1, 0, 0, -20, 0, 1, 0, 0, 0, 0, 1, 0]
        bones = [{"inverse_bind_matrix": inverse0}, {"inverse_bind_matrix": inverse1}]
        worlds = [local_matrix([0, 0, 0], [1, 1, 1], [13, 0, 0]),
                  local_matrix([0, 0, 0], [1, 1, 1], [27, 0, 0])]
        envelope = [[{"joint_index": 0, "weight": 1}],
                    [{"joint_index": 0, "weight": .5}, {"joint_index": 1, "weight": .5}]]
        p = palette_matrices(bones, worlds, envelope)
        self.assertEqual(p[0][0, 3], 13)
        self.assertEqual(p[1][0, 3], 5)
        mesh = {"source_positions": [[1, 2, 3], [1, 2, 3]], "source_normals": [[0, 1, 0]] * 2,
                "palette_indices": [0, 1], "envelopes": envelope}
        positions, normals = skin_source_mesh(mesh, bones, worlds)
        np.testing.assert_allclose(positions, [[14, 2, 3], [6, 2, 3]])
        np.testing.assert_allclose(normals, [[0, 1, 0], [0, 1, 0]])

    def test_normal_inverse_transpose_for_nonuniform_scale(self):
        mesh = {"source_positions": [[1, 1, 0]], "source_normals": [[1, 1, 0]],
                "palette_indices": [0], "envelopes": [[{"joint_index": 0, "weight": 1}]]}
        _, normal = skin_source_mesh(mesh, [{"inverse_bind_matrix": None}],
                                     [local_matrix([0, 0, 0], [2, 1, 1], [0, 0, 0])])
        np.testing.assert_allclose(normal, [[1 / math.sqrt(5), 2 / math.sqrt(5), 0]])


if __name__ == "__main__":
    unittest.main()
