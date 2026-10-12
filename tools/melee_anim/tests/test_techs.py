"""Synthetic ground-effect alpha/geometry tests; no original game fixtures."""
from pathlib import Path
import unittest
from PIL import Image
import numpy as np

from tools.melee_anim.attacks import common_submotions, attack_label
from tools.melee_anim.techs import TECH_LABELS, tech_label, ground_effect
from tools.melee_anim.ground_effects import GroundEffect, effect_texture_rgb, matched_tree, rgba_triangles
from tools.melee_anim.fighter_colors import blend_fighter_color, color_samples, intangible_end_tick, tech_color_animation
from tools.melee_anim.preview import camera_basis, fit_knockdown_camera
from tools.melee_anim.hsd import FormatError


class TechTests(unittest.TestCase):
    def test_visible_effect_bounds_exclude_transparent_geometry_padding(self):
        effect=GroundEffect.__new__(GroundEffect)
        positions=np.array([[-1000.,-1000.,0.],[1000.,-1000.,0.],[0.,1000.,0.]])
        effect.geometry=lambda tick,anchor,view:[({},positions+anchor)]
        layer=Image.new('RGBA',(512,512))
        for x in range(252,260):
            for y in range(252,260):layer.putpixel((x,y),(0,255,0,255))
        effect.render=lambda *args:layer
        bounds=effect.visible_bounds([0,1],[[0,0,0]],np.eye(3))
        self.assertEqual(bounds.shape,(8,3))
        self.assertLess(np.ptp(bounds[:,0]),100)
        self.assertLess(np.ptp(bounds[:,1]),100)
        effect.render=lambda *args:Image.new('RGBA',(512,512))
        self.assertEqual(effect.visible_bounds([0],[[0,0,0]],np.eye(3)).shape,(0,3))

    def test_alpha_only_tev_preserves_green_texture_and_active_color_generator(self):
        rgb=np.array([[[0.,1.,0.]]]); konst=np.zeros(3)
        np.testing.assert_array_equal(effect_texture_rgb(rgb,konst,0x8000007F),rgb)
        np.testing.assert_array_equal(effect_texture_rgb(rgb,konst,0xC0000077),np.zeros_like(rgb))
        np.testing.assert_array_equal(rgb,[[[0.,1.,0.]]])

    def test_projected_fighter_fit_is_centered_at_rotated_angles(self):
        cloud=np.array([[-2.,0.,0.],[3.,0.,0.],[-1.,7.,0.],[8.,1.,10.]])
        for yaw,pitch,roll in ((0,0,0),(45,20,0),(-80,0,35)):
            view=camera_basis(yaw,pitch,roll)
            center,scale=fit_knockdown_camera(cloud,view,256)
            projected=(cloud-center)@view
            np.testing.assert_allclose((projected.min(0)+projected.max(0))[:2],0,atol=1e-12)
            self.assertAlmostEqual(np.ptp(projected[:,:2],axis=0).max()*scale,256*.82)

    def test_impact_grows_with_the_shared_camera_scale(self):
        effect=GroundEffect.__new__(GroundEffect)
        effect.kind='missed';effect.tex_tracks={}
        tex={'offset':1,'id':0,'konst':[255]*4,'tev_active':0x8000007F,'blend':1}
        effect.materials={2:{'offset':2,'textures':[tex]}}
        effect.textures={1:np.tile(np.array([0,255,0,255],dtype='uint8'),(2,2,1))}
        mesh={'material':2,'colors':[[1.,1.,1.,1.]]*3,'uvs':[[0,0]]*3,'triangles':[[0,1,2]]}
        positions=np.array([[-1.,-1.,0.],[1.,-1.,0.],[0.,1.,0.]])
        effect.geometry=lambda tick,anchor,view:[(mesh,positions+anchor)]
        small=effect.render(0,[[0,0,0]],np.eye(3),64,np.zeros(3),3)
        large=effect.render(0,[[0,0,0]],np.eye(3),64,np.zeros(3),6)
        a,b=small.getchannel('A').getbbox(),large.getchannel('A').getbbox()
        self.assertGreater(b[2]-b[0],a[2]-a[0])
        self.assertLessEqual(abs((b[3]-b[1])-2*(a[3]-a[1])),1)
        self.assertEqual(large.getpixel((32,32)),(0,255,0,255))

    def test_source_color_wait_goto_and_terminal_reset(self):
        class Script:
            words={0:18<<26,8:(19<<26)|4,16:(11<<26)|4,20:12<<26,24:(11<<26)|2,28:7<<26}
            def u32(self,at):return self.words[at]
            def read(self,at,size):return bytes([255,255,255,90 if at==4 else 40])
            def pointer(self,at):return 0
        samples=color_samples(Script(),0,9)
        self.assertEqual([int(c[3]) for c in samples],[77,65,52,40,28,15,77,65,52])
        class EntryFlash(Script):
            words={0:18<<26,8:(11<<26)|2,12:10<<26}
        samples=color_samples(EntryFlash(),0,4)
        self.assertEqual(int(samples[0][3]),90)
        self.assertEqual(int(samples[1][3]),90)
        self.assertIsNone(samples[2]);self.assertIsNone(samples[3])
        class Invalid(Script):
            words={0:7<<26}
        with self.assertRaises(FormatError):color_samples(Invalid(),0,1)

    def test_fighter_color_preserves_coverage_and_knockdown_flash_selection(self):
        image=Image.new('RGBA',(2,1),(10,20,30,255));image.putpixel((0,0),(10,20,30,0))
        flashed=blend_fighter_color(image,np.array([255,255,255,120]))
        self.assertEqual(flashed.getchannel('A').tobytes(),image.getchannel('A').tobytes())
        self.assertGreater(flashed.getpixel((1,0))[0],image.getpixel((1,0))[0])
        self.assertEqual(tech_color_animation('tech-199'),120)
        self.assertEqual(tech_color_animation('tech-201_source'),2)
        self.assertIsNone(tech_color_animation('tech-200'))
        self.assertIsNone(tech_color_animation('tech-183'))

    def test_flash_ends_at_source_hit_status_reset_including_shared_script(self):
        commands=[{'opcode':26,'first_word':'0x68000002'},
                  {'opcode':2,'timer_ticks':24},
                  {'opcode':26,'first_word':'0x68000000'}]
        self.assertEqual(intangible_end_tick({'frames':40,'script':{'commands':commands}}),24)
        self.assertEqual(intangible_end_tick({'frames':40,'script':{'reachable_blocks':[{'commands':commands}]}}),24)

    def test_identity_face_direction_and_impact_are_separate_from_attacks(self):
        common=common_submotions(Path(__file__).resolve().parents[3])
        expected={183:'DownBoundU',184:'DownWaitU',191:'DownBoundD',192:'DownWaitD',
                  199:'Passive',200:'PassiveStandF',201:'PassiveStandB'}
        for aid,name in expected.items():
            self.assertEqual(common[aid],name)
            self.assertEqual(ground_effect(f'tech-{aid}'),TECH_LABELS[name][1])
            self.assertIsNone(attack_label(name))
            self.assertIsNotNone(tech_label(name))
        self.assertIsNone(ground_effect('attack-199'))
        self.assertIsNone(tech_label('DownFowardU'),'missed-tech getup rolls are not successful tech rolls')

    def test_texture_alpha_and_vertex_colors_have_no_opaque_background(self):
        pixels=np.full((2,2,4),255,dtype='uint8')
        positions=np.array([[2.,2.],[12.,2.],[2.,12.]])
        colors=np.array([[1.,0.,0.,.5]]*3)
        im=rgba_triangles(16,positions,np.zeros((3,2)),colors,[[0,1,2]],pixels)
        self.assertEqual(im.getpixel((0,0)),(0,0,0,0))
        self.assertEqual(im.getpixel((4,4)),(255,0,0,127))
        pixels[:,:,3]=0
        im=rgba_triangles(16,positions,np.zeros((3,2)),colors,[[0,1,2]],pixels)
        self.assertEqual(np.asarray(im)[:,:,3].max(),0)

    def test_effect_tree_matching_and_malformed_topology(self):
        class Tree:
            def __init__(self,pointers):self.pointers=pointers
            def pointer(self,at):return self.pointers.get(at)
        bones=[{'index':0,'parent':None},{'index':1,'parent':0},{'index':2,'parent':0}]
        seen=[]
        matched_tree(Tree({100:120,124:140}),bones,100,lambda i,a:seen.append((i,a)))
        self.assertEqual(seen,[(0,100),(1,120),(2,140)])
        for pointers in ({100:100},{100:120,124:140,144:160}):
            with self.assertRaises(FormatError):matched_tree(Tree(pointers),bones,100,lambda i,a:None)


if __name__=='__main__':unittest.main()
