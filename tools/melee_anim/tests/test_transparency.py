"""True coverage alpha, palette index safety, resizing and GIF disposal."""
from io import BytesIO
import os
import unittest

import numpy as np
from PIL import Image, ImageDraw

from tools.melee_anim.downloads import SIZES, resize_gif, resize_png
from tools.melee_anim.gif_export import encode_frames, expand_ticks, quantize_rgba
from tools.melee_anim.preview import camera_basis, render_frame


class TransparencyTests(unittest.TestCase):
    def sprites(self):
        frames = []
        for box, color in [((4,4,7,7),(0,0,0,255)),((22,22,25,25),(34,38,46,255))]:
            frame = Image.new('RGBA',(32,32),(34,38,46,0))
            ImageDraw.Draw(frame).rectangle(box,fill=color)
            frames.append(frame)
        return frames

    def test_reserved_transparency_keeps_black_and_background_colored_geometry(self):
        frames = quantize_rgba(self.sprites())
        self.assertEqual(frames[0].info['transparency'],0)
        self.assertNotEqual(frames[0].getpixel((5,5)),0)
        self.assertNotEqual(frames[1].getpixel((24,24)),0)
        data = encode_frames(frames,[20,40],0)
        with Image.open(BytesIO(data)) as im:
            self.assertEqual(im.n_frames,2)
            self.assertEqual(im.info['loop'],0)
            self.assertEqual(im.convert('RGBA').getpixel((5,5)),(0,0,0,255))
            self.assertEqual(im.convert('RGBA').getpixel((0,0))[3],0)
            im.seek(1)
            self.assertEqual(im.convert('RGBA').getpixel((5,5))[3],0,'previous pose must be cleared')
            self.assertEqual(im.convert('RGBA').getpixel((24,24)),(34,38,46,255))
        with Image.open(BytesIO(expand_ticks(data))) as im:
            self.assertEqual(im.n_frames,3)
            for i in range(3):
                im.seek(i); self.assertEqual(im.info['duration'],20)
                self.assertEqual(im.convert('RGBA').getpixel((0,0))[3],0)

    def test_all_sizes_preserve_alpha_delay_and_no_matte_or_trails(self):
        data = encode_frames(quantize_rgba(self.sprites()),[20,40],None)
        for size in SIZES:
            with Image.open(BytesIO(resize_gif(data,size))) as im:
                self.assertNotIn('loop',im.info)
                self.assertEqual(im.n_frames,2)
                self.assertEqual(im.convert('RGBA').getpixel((0,0))[3],0)
                black = (round(5.5*size/32),round(5.5*size/32))
                self.assertEqual(im.convert('RGBA').getpixel(black),(0,0,0,255))
                im.seek(1);self.assertEqual(im.info['duration'],40)
                self.assertEqual(im.convert('RGBA').getpixel(black)[3],0)
            png = BytesIO();self.sprites()[0].save(png,format='PNG')
            with Image.open(BytesIO(resize_png(png.getvalue(),size))) as im:
                pixels = np.array(im)
                self.assertEqual(im.getpixel((0,0))[3],0)
                self.assertTrue(np.all(pixels[pixels[:,:,3]>0,:3]==0),'no gray matte on black edges')

    def test_rasters_use_coverage_not_rgb_and_keep_outline_alpha(self):
        mesh = {'material_index':0,'uvs':[[0,0]]*3,'triangles':[[0,1,2]]}
        model = {'meshes':[mesh],'materials':[{'textures':[],'diffuse_rgba':[34,38,46,255],'unlit':True}]}
        positions=np.array([[-1,-1,0],[1,-1,0],[0,1,0]],dtype=float)
        normals=np.tile([0.,0.,1.],(3,1))
        def check(renderer):
            im=renderer(model,[(positions,normals)],{},camera_basis(0),32,32,np.zeros(3),12,(34,38,46,0))
            self.assertEqual(im.getpixel((0,0))[3],0)
            self.assertEqual(im.getpixel((16,16)),(34,38,46,255))
        check(render_frame)
        if os.name=='nt':
            from tools.melee_anim.native_raster import NativeRaster
            raster=NativeRaster(32)
            try:
                check(raster.render)
                model['outline_rgba']=[255,255,255,128]
                im=raster.render(model,[(positions,normals)],{},camera_basis(0),32,32,np.zeros(3),12,(34,38,46,0))
                self.assertEqual(set(np.array(im)[:,:,3].flat),{0,128,255})
            finally:raster.close()


if __name__=='__main__':unittest.main()
