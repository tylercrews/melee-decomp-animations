"""Synthetic geometry checks; no original game assets or visible windows."""
import os
import unittest
import numpy as np
from tools.melee_anim.preview import camera_basis
from tools.melee_anim.native_raster import NativeRaster


@unittest.skipUnless(os.name == "nt", "Windows memory-bitmap OpenGL backend")
class NativeRasterTests(unittest.TestCase):
    def test_unlit_costume_color_does_not_depend_on_normals(self):
        mesh = {"material_index": 0, "uvs": [[0, 0]]*3, "triangles": [[0, 1, 2]]}
        rgba = [210, 50, 90, 255]
        model = {"meshes": [mesh], "materials": [{"textures": [], "diffuse_rgba": rgba, "unlit": True}]}
        p = np.array([[-1, -1, 0], [1, -1, 0], [0, 1, 0]], dtype=float)
        raster = NativeRaster(32)
        try:
            for direction in ([0., 0., 1.], [0., 0., -1.]):
                image = raster.render(model, [(p, np.tile(direction, (3, 1)))], {},
                                      camera_basis(0), 32, 32, np.zeros(3), 12, (0, 0, 0, 255))
                self.assertEqual(np.asarray(image)[16, 16].tolist(), rgba)
        finally:
            raster.close()

    def test_depth_clockwise_culling_and_hidden_drawable(self):
        mesh = {"material_index": 0, "uvs": [[0, 0]]*3, "triangles": [[0, 2, 1]], "cull_flags": 0x8000}
        model = {"meshes": [mesh, {**mesh, "material_index": 1}],
                 "materials": [{"textures": [], "diffuse_rgba": [255, 0, 0, 255]},
                               {"textures": [], "diffuse_rgba": [0, 0, 255, 255]}]}
        p = np.array([[-1, -1, 1], [1, -1, 1], [0, 1, 1]], dtype=float)
        n = np.tile([0., 0., 1.], (3, 1))
        raster = NativeRaster(32)
        def draw(poses):
            return np.asarray(raster.render(model, poses, {}, camera_basis(0), 32, 32,
                                           np.zeros(3), 12, (0, 0, 0, 255)))[16, 16]
        try:
            color = draw([(p, n), (p-[0, 0, 1], n)])
            self.assertGreater(color[0], 200)
            self.assertEqual(color[2], 0)
            color = draw([(None, None), (p-[0, 0, 1], n)])
            self.assertGreater(color[2], 200)
            model["meshes"][1]["cull_flags"] = 0x4000
            self.assertEqual(draw([(None, None), (p, n)])[:3].tolist(), [0, 0, 0])
        finally:
            raster.close()


if __name__ == "__main__":
    unittest.main()
