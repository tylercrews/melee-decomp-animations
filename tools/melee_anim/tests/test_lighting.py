import unittest

import numpy as np

from tools.melee_anim.lighting import lighting_factors


class LightingTests(unittest.TestCase):
    def test_source_material_ambient_and_directional_saturation(self):
        rig = {'lights':[{'flags':4,'rgba':[179]*3+[255],'position':None},
                         {'flags':13,'rgba':[255]*4,'position':[0,0,1]}]}
        mat = {'render_mode':4,'ambient_rgba':[179]*3+[255]}
        diffuse, specular = lighting_factors(mat, [[0,0,-1],[0,0,1]], np.eye(3), rig)
        np.testing.assert_allclose(diffuse[0], (179/255)**2)
        np.testing.assert_array_equal(diffuse[1], [1]*3)
        np.testing.assert_array_equal(specular, np.zeros((2,3)))

    def test_gx_specular_rational_attenuation_and_material_flags(self):
        rig = {'lights':[{'flags':13,'rgba':[255]*4,'position':[0,0,1]}]}
        mat = {'render_mode':8,'shininess':50}
        n = [[0,0,1],[np.sqrt(.75),0,.5],[0,0,-1]]
        _, spec = lighting_factors(mat, n, np.eye(3), rig)
        np.testing.assert_allclose(spec[:,0], [1,.25/(25-24*.25),0])
        mat['shininess'] = 200
        self.assertLess(lighting_factors(mat,n,np.eye(3),rig)[1][1,0],spec[1,0])
        mat['unlit'] = True
        diffuse, spec = lighting_factors(mat,n,np.eye(3),rig)
        np.testing.assert_array_equal(diffuse, np.ones((3,3)))
        np.testing.assert_array_equal(spec, np.zeros((3,3)))

    def test_specular_tracks_view_direction_and_ignores_hidden_lights(self):
        rig = {'lights':[{'flags':13,'rgba':[255]*4,'position':[0,0,1]}]}
        mat = {'render_mode':8,'shininess':50}
        before = lighting_factors(mat,[[0,0,1]],np.eye(3),rig)[1]
        view = np.array([[0,0,1],[0,1,0],[-1,0,0]])
        self.assertLess(lighting_factors(mat,[[0,0,1]],view,rig)[1][0,0],before[0,0])
        rig['lights'][0]['flags'] |= 32
        np.testing.assert_array_equal(lighting_factors(mat,[[0,0,1]],view,rig)[1],np.zeros((1,3)))
