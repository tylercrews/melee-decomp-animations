"""Source outline pass/visibility/transparent-downsampling regressions."""
import os
import unittest
from io import BytesIO
import numpy as np
from PIL import Image
from tools.melee_anim.game_watch import outline_color
from tools.melee_anim.roster import visible_drawables
from tools.melee_anim.preview import render_frame
from tools.melee_anim.downloads import resize_gif


class GameWatchTests(unittest.TestCase):
    def test_outline_alpha_is_rgb_overlay_not_transparency(self):
        self.assertEqual(outline_color([0,0,0,255],[255,255,255,128]),[128,128,128,255])
        self.assertEqual(outline_color([110,0,0,255],[255,255,255,128]),[183,128,128,255])

    def test_outline_alternatives_follow_body_visibility(self):
        model={'visibility':{'groups':[[[0],[1]],[[2]]], 'outline_groups':[[[3],[4]],[[5]]],
                             'defaults':[0,-1], 'base':[0,1,2,3,4,5,6]}}
        self.assertEqual(visible_drawables(model),{0,3,6})
        self.assertEqual(visible_drawables(model,[1,0]),{1,2,4,5,6})
        self.assertEqual(visible_drawables(model,[-1,-1]),{6})

    def test_source_geometry_border_survives_quarter_size_gif(self):
        mesh={'material_index':0,'uvs':[[0,0]]*4,'triangles':[[0,1,2],[0,2,3]]}
        outline={**mesh,'material_index':1,'outline_pass':True}
        model={'meshes':[mesh,outline], 'materials':[
            {'textures':[],'diffuse_rgba':[0,0,0,255],'unlit':True},
            {'textures':[],'diffuse_rgba':[128,128,128,255],'unlit':True}],
            'outline_geometry':True,'outline_rgba':[255,255,255,128]}
        square=lambda extent,z:np.array([[-extent,-extent,z],[extent,-extent,z],[extent,extent,z],[-extent,extent,z]])
        normal=np.tile([0,0,1.],(4,1));posed=[(square(1,0),normal),(square(1.2,-.1),normal)]
        def check(render):
            im=render(model,posed,{},np.eye(3),512,512,np.zeros(3),180,(34,38,46,0))
            self.assertEqual(im.getpixel((256,256)),(0,0,0,255))
            self.assertEqual(im.getpixel((50,256)),(128,128,128,255))
            self.assertEqual(im.getpixel((0,0))[3],0)
            # Use the application's alpha-aware GIF encoder, including resize.
            from tools.melee_anim.gif_export import encode_frames,quantize_rgba
            data=resize_gif(encode_frames(quantize_rgba([im]),[20],0),128)
            with Image.open(BytesIO(data)) as saved:
                rgba=saved.convert('RGBA')
                self.assertEqual(rgba.getpixel((12,64)),(128,128,128,255))
                self.assertEqual(rgba.getpixel((64,64)),(0,0,0,255))
                self.assertEqual(rgba.getpixel((0,0))[3],0)
        check(render_frame)
        if os.name=='nt':
            from tools.melee_anim.native_raster import NativeRaster
            raster=NativeRaster(512)
            try:check(raster.render)
            finally:raster.close()


if __name__=='__main__':unittest.main()
