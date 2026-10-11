import math
import unittest

import numpy as np

from tools.melee_anim.preview import camera_basis, deform, joint_visibility, pose_matrices, reflection_uv, render_frame, runtime_root_rotation, srt_matrix, texture_uv
from tools.melee_anim.motions import Track
import struct


class PreviewTests(unittest.TestCase):
    def test_translucent_black_prop_keeps_alpha_in_python_raster(self):
        mesh={'material_index':0,'uvs':[[0,0]]*3,'triangles':[[0,1,2]]}
        mat={'textures':[],'diffuse_rgba':[0,0,0,255],'unlit':True,'alpha':.25,'item_alpha_blend':True}
        p=np.array([[-1.,-1,0],[1.,-1,0],[0.,1,0]])
        im=render_frame({'meshes':[mesh],'materials':[mat]},[(p,np.tile([0.,0,1],(3,1)))],{},np.eye(3),32,32,np.zeros(3),12,(0,0,0,0))
        self.assertEqual(im.getpixel((16,16)),(0,0,0,64))
        self.assertEqual(im.getpixel((0,0))[3],0)

    def test_full_eye_blend_matches_replace_without_gray_diffuse_tint(self):
        tex={'coordinate_type':0,'flags':0x30010,'blend':1.,'image_file':'eye','texture_matrix':np.eye(4).tolist()}
        mat={'textures':[tex],'diffuse_rgba':[179,179,179,255],'diffuse_texture_only':True}
        mesh={'material_index':0,'uvs':[[0,0]]*3,'triangles':[[0,1,2]]}
        p=np.array([[-1.,-1,0],[1.,-1,0],[0.,1,0]])
        pixels=np.tile(np.array([250,210,75,255],dtype='uint8'),(2,2,1))
        def draw():
            return np.asarray(render_frame({'meshes':[mesh],'materials':[mat]},[(p,np.tile([0.,0,1],(3,1)))],{'eye':pixels},np.eye(3),32,32,np.zeros(3),12,(0,0,0,0)))
        blended=draw()
        tex['flags']=0x50010
        np.testing.assert_array_equal(blended,draw())
        tex['flags']=0x30010;mat['diffuse_texture_only']=False
        self.assertGreater(int(blended[16,16,0]),int(draw()[16,16,0]))

    def test_reflection_coordinates_follow_camera_normals_and_hsd_bias(self):
        normals=np.eye(3)
        np.testing.assert_allclose(reflection_uv(normals,np.eye(3)),[[1,.5],[.5,0],[.5,.5]])
        np.testing.assert_allclose(reflection_uv([[2.,0,0]],camera_basis(90)),[[.5,.5]],atol=1e-12)

    def test_opted_reflection_texture_replaces_gray_material_in_python_raster(self):
        tex={'coordinate_type':1,'flags':0x50081,'image_file':'visor','texture_matrix':np.eye(4).tolist()}
        material={'textures':[tex],'diffuse_rgba':[164,164,164,255],'unlit':True,'reflection_texture_preview':True}
        mesh={'material_index':0,'uvs':[[0,0]]*3,'triangles':[[0,1,2]]}
        positions=np.array([[-1.,-1,0],[1.,-1,0],[0.,1,0]])
        pixels=np.tile(np.array([0,255,0,255],dtype='uint8'),(2,2,1))
        model={'meshes':[mesh],'materials':[material]}
        image=render_frame(model,[(positions,np.tile([0.,0,1],(3,1)))],{'visor':pixels},np.eye(3),32,32,np.zeros(3),12,(0,0,0,0))
        self.assertEqual(image.getpixel((16,16)),(0,255,0,255))
        material['reflection_texture_preview']=False
        unchanged=render_frame(model,[(positions,np.tile([0.,0,1],(3,1)))],{'visor':pixels},np.eye(3),32,32,np.zeros(3),12,(0,0,0,0))
        self.assertEqual(unchanged.getpixel((16,16)),(164,164,164,255))

    def test_fighter_root_width_and_facing_precede_child_pose_and_skinning(self):
        bones = [{"index": 0, "parent": None, "flags": 8, "rotation": [0, 0, 0],
                  "position": [0, 0, 0], "scale": [1, 1, 1], "inverse_bind_matrix": None},
                 {"index": 1, "parent": 0, "flags": 8, "rotation": [0, 0, math.pi/2],
                  "position": [2, 0, 3], "scale": [1, 1, 1], "inverse_bind_matrix": None}]
        mesh = {"source_positions": [[0, 1, 0]], "source_normals": [[0, 1, 0]],
                "palette_indices": [0], "envelopes": [[{"joint_index": 1, "weight": 1}]]}
        for action, sign in [("victory1", -1), ("results-clap", -1), ("taunt", 1)]:
            matrices = pose_matrices(bones, [], 0, root_scale=[.01, 1, 1],
                                     root_rotation=runtime_root_rotation({"fighter_kind": 24}, action))
            positions, normals = deform(mesh, matrices, bones)
            # Child rotation/translation is flattened locally, then faced.
            np.testing.assert_allclose(positions, [[sign*3, 0, -sign*.01]], atol=1e-12)
            np.testing.assert_allclose(normals, [[0, 0, sign]], atol=1e-12)
        self.assertEqual(bones[0]["scale"], [1, 1, 1])
        self.assertEqual(bones[0]["rotation"], [0, 0, 0])
        self.assertIsNone(runtime_root_rotation({"fighter_kind": 0}, "victory1"))

    def test_unlit_costume_color_does_not_depend_on_normals(self):
        mesh = {"material_index": 0, "uvs": [[0, 0]]*3, "triangles": [[0, 1, 2]]}
        rgba = [210, 50, 90, 255]
        model = {"meshes": [mesh], "materials": [{"textures": [], "diffuse_rgba": rgba, "unlit": True}]}
        p = np.array([[-1, -1, 0], [1, -1, 0], [0, 1, 0]], dtype=float)
        for direction in ([0., 0., 1.], [0., 0., -1.]):
            image = render_frame(model, [(p, np.tile(direction, (3, 1)))], {},
                                 camera_basis(0), 16, 16, np.zeros(3), 6, (0, 0, 0, 255))
            self.assertEqual(np.asarray(image)[8, 8].tolist(), rgba)

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
