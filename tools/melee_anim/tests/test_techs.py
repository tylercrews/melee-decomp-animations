"""Synthetic ground-effect alpha/geometry tests; no original game fixtures."""
from pathlib import Path
import unittest
import numpy as np

from tools.melee_anim.attacks import common_submotions, attack_label
from tools.melee_anim.techs import TECH_LABELS, tech_label, ground_effect
from tools.melee_anim.ground_effects import matched_tree, rgba_triangles
from tools.melee_anim.hsd import FormatError


class TechTests(unittest.TestCase):
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
