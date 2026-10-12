"""Synthetic costume texture requests; no original asset bytes."""
import uuid
import shutil
import struct
import unittest
from pathlib import Path
from PIL import Image
from tools.melee_anim.fighter_textures import FighterTextures


class FighterTextureTests(unittest.TestCase):
    def test_requested_frame_is_evaluated_not_used_as_image_index(self):
        build=Path(__file__).resolve().parents[3]/'build/melee_anim/tests'
        build.mkdir(parents=True,exist_ok=True)
        folder=build/f'textures_{uuid.uuid4().hex}'
        folder.mkdir()
        try:
            for i in range(3):Image.new('RGBA',(2,2),(i*80,0,0,255)).save(folder/f'{i}.png')
            # Constant keys: frame zero -> image 0, frame 2 -> image 1,
            # frame 5 -> image 2. The source frame and image ID differ.
            raw=bytes([0x21])+struct.pack('<f',0)+bytes([2])+struct.pack('<f',1)+bytes([3])+struct.pack('<f',2)
            texture={'global_tobj_index':7,'image_file':'0.png','animation_images':['0.png','1.png','2.png'],
                     'animation_tracks':[dict(channel=1,startframe=0,frac_value=0,frac_slope=0,data=raw.hex())]}
            model={'texture_script_map':[7],'materials':[{'textures':[texture]}]}
            request={'offset':4,'opcode':40,'first_word':'0xa0000002',
                     'texture_animation':dict(index=0,index2=0,both=False,frame=2)}
            script={'commands':[{'offset':0,'opcode':1,'first_word':'0x04000003','timer_ticks':3},request]}
            textures={};face=FighterTextures(model,dict(frames=10,script=script),folder,textures)
            face.apply(2.9);self.assertEqual(texture['image_file'],'0.png')
            face.apply(3);self.assertEqual(texture['image_file'],'1.png')
            face.apply(9);self.assertEqual(texture['image_file'],'1.png')
            face.apply(0);self.assertEqual(texture['image_file'],'0.png')
            face=FighterTextures(model,dict(frames=10,script={},texture_initial_scripts=[(script,10)]),folder,textures)
            face.apply(0);self.assertEqual(texture['image_file'],'1.png')
            self.assertEqual(len(textures),3)
        finally:
            if not folder.resolve().is_relative_to(build.resolve()):raise RuntimeError('Unexpected cleanup path')
            shutil.rmtree(folder)


if __name__=='__main__':unittest.main()
