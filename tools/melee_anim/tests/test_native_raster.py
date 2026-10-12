"""Synthetic geometry checks; no original game assets or visible windows."""
import os
import unittest
import numpy as np
from tools.melee_anim.preview import camera_basis
from tools.melee_anim.native_raster import NativeRaster


@unittest.skipUnless(os.name == "nt", "Windows memory-bitmap OpenGL backend")
class NativeRasterTests(unittest.TestCase):
    def test_translucent_black_prop_keeps_true_alpha_without_color_keying(self):
        mesh={'material_index':0,'uvs':[[0,0]]*3,'triangles':[[0,1,2]]}
        mat={'textures':[],'diffuse_rgba':[0,0,0,255],'unlit':True,'alpha':.25,'item_alpha_blend':True}
        p=np.array([[-1.,-1,0],[1.,-1,0],[0.,1,0]])
        raster=NativeRaster(32)
        try:
            im=raster.render({'meshes':[mesh],'materials':[mat]},[(p,np.tile([0.,0,1],(3,1)))],{},np.eye(3),32,32,np.zeros(3),12,(0,0,0,0))
            pixel=im.getpixel((16,16))
            self.assertEqual(pixel[:3],(0,0,0));self.assertLessEqual(abs(pixel[3]-64),1)
            self.assertEqual(im.getpixel((0,0))[3],0)
        finally:raster.close()

    def test_opted_reflection_texture_is_visible_in_native_raster(self):
        tex={'coordinate_type':1,'flags':0x50081,'image_file':'visor','texture_matrix':np.eye(4).tolist()}
        mat={'textures':[tex],'diffuse_rgba':[164,164,164,255],'unlit':True,'reflection_texture_preview':True}
        mesh={'material_index':0,'uvs':[[0,0]]*3,'triangles':[[0,1,2]]}
        p=np.array([[-1.,-1,0],[1.,-1,0],[0.,1,0]])
        pixels=np.tile(np.array([0,255,0,255],dtype='uint8'),(2,2,1))
        raster=NativeRaster(32)
        try:
            im=raster.render({'meshes':[mesh],'materials':[mat]},[(p,np.tile([0.,0,1],(3,1)))],{'visor':pixels},np.eye(3),32,32,np.zeros(3),12,(0,0,0,0))
            self.assertEqual(im.getpixel((16,16)),(0,255,0,255))
        finally:raster.close()

    def test_copy_hat_diffuse_blend_keeps_color_instead_of_specular_mask(self):
        textures={'color':np.tile(np.array([0,255,0,255],dtype='uint8'),(2,2,1)),
                  'mask':np.full((2,2,4),255,dtype='uint8')}
        common={'coordinate_type':0,'source':4,'texture_matrix':np.eye(4).tolist(),'blend':1}
        diffuse={**common,'flags':0x30010,'image_file':'color'}
        specular={**common,'flags':0x40020,'image_file':'mask'}
        mat={'textures':[diffuse,specular],'diffuse_rgba':[179,179,179,255],'unlit':True,'copy_diffuse_only':True}
        mesh={'material_index':0,'uvs':[[0,0]]*3,'triangles':[[0,1,2]]}
        p=np.array([[-1.,-1,0],[1.,-1,0],[0.,1,0]])
        raster=NativeRaster(32)
        try:
            im=raster.render({'meshes':[mesh],'materials':[mat]},[(p,np.tile([0.,0,1],(3,1)))],textures,np.eye(3),32,32,np.zeros(3),12,(0,0,0,0))
            self.assertEqual(im.getpixel((16,16)),(0,255,0,255))
            # Ordinary eye materials opt into the same full-BLEND semantics.
            mat.pop('copy_diffuse_only');mat['diffuse_texture_only']=True
            im=raster.render({'meshes':[mesh],'materials':[mat]},[(p,np.tile([0.,0,1],(3,1)))],textures,np.eye(3),32,32,np.zeros(3),12,(0,0,0,0))
            self.assertEqual(im.getpixel((16,16)),(0,255,0,255))
        finally:raster.close()

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
