from io import BytesIO
import json
from pathlib import Path
import shutil
import threading
import unittest
import uuid
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen
from zipfile import ZipFile

import numpy as np
from PIL import Image

from tools.melee_anim.downloads import DownloadCatalog
from tools.melee_anim.player_server import make_server
from tools.melee_anim.preview import camera_basis, fit_camera
from tools.melee_anim.rotations import RotationCache, camera_angles, marked_angle


class CameraTests(unittest.TestCase):
    def test_basis_axes_order_and_orthonormality(self):
        np.testing.assert_array_equal(camera_basis(0), np.eye(3))
        # Basis columns describe the camera's right/up/forward world vectors.
        np.testing.assert_allclose(camera_basis(90)[:, 2], [1, 0, 0], atol=1e-12)
        np.testing.assert_allclose(camera_basis(0, 90)[:, 2], [0, -1, 0], atol=1e-12)
        np.testing.assert_allclose(camera_basis(0, 0, 90)[:, 0], [0, 1, 0], atol=1e-12)
        view = camera_basis(73, -34, 15)
        np.testing.assert_allclose(view.T @ view, np.eye(3), atol=1e-12)
        self.assertAlmostEqual(np.linalg.det(view), 1)
        np.testing.assert_allclose(view, camera_basis(73) @ camera_basis(0, -34) @ camera_basis(0, 0, 15))
        for yaw in (float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                camera_basis(yaw)

    def test_angles_and_filenames(self):
        self.assertEqual(camera_angles(180, -0., '45'), (-180, 0, 45))
        self.assertEqual(marked_angle('clip.gif', (10, -45, 0)), 'clip-view-x10-y-45-z0.gif')
        self.assertEqual(marked_angle('clip.gif', (0, 0, 0)), 'clip.gif')
        for value in (181, -181, float('nan'), float('inf'), 'oops'):
            with self.assertRaises(ValueError):
                camera_angles(value)

    def test_whole_clip_framing_keeps_pivot_and_contains_all_rotated_samples(self):
        cloud = np.array([[-8., -2, 1], [3, 6, -1], [-6, 3, 7], [2, -1, -4]])
        center, _ = fit_camera(cloud, camera_basis(0), 256)
        for angles in [(0, 90, 0), (30, 45, 15), (-90, 120, 180)]:
            view = camera_basis(angles[1], angles[0], angles[2])
            pivot, scale = fit_camera(cloud, view, 256)
            np.testing.assert_array_equal(center, pivot)
            projected = (cloud-pivot) @ view*scale
            self.assertTrue((np.abs(projected[:, :2]) <= 256*.41+1e-10).all())
        with self.assertRaises(ValueError):
            fit_camera(np.zeros((4, 3)), camera_basis(0), 256)


class RotationCacheTests(unittest.TestCase):
    def setUp(self):
        self.build = Path('build/melee_anim_tests').resolve()
        self.repo = self.build/f'rotation_{uuid.uuid4().hex}'
        self.root = self.repo/'build/melee_anim/preview'
        self.folder = self.root/'synthetic/costume_00/results-clap_source'
        self.folder.mkdir(parents=True)
        self.model = self.repo/'build/melee_anim/exported/synthetic/costume_00/model.json'
        self.model.parent.mkdir(parents=True)
        texture = {'image_file': 'color.png'}
        self.model.write_text(json.dumps({'fighter_kind': 0, 'materials': [{'textures': [texture]}]}))
        Image.new('RGBA', (8, 8), 'blue').save(self.model.parent/'color.png')
        files = self.repo/'orig/GALE01/files'
        files.mkdir(parents=True)
        (files/'fake.dat').write_bytes(b'no game assets')
        (self.repo/'build/melee_anim/motions.json').write_text(json.dumps({'results': [{'fighter_kind': 0, 'results_archive': 'fake.dat'}]}))
        self.manifest = {'sample_source_times': [0, 1, 2], 'fps': 50}
        (self.folder/'preview-manifest.json').write_text(json.dumps(self.manifest))
        Image.new('RGB', (16, 16), 'red').save(self.folder/'preview.gif')
        for i in range(3):
            Image.new('RGBA', (16, 16), 'red').save(self.folder/f'frame_{i:04d}.png')
        self.clip = {'character': 'synthetic', 'action_key': 'results-clap_source', 'costume_id': 0, 'fps': 50,
                     'download_name': 'synthetic.gif', 'gif': 'synthetic/costume_00/results-clap_source/preview.gif',
                     'frames': [f'synthetic/costume_00/results-clap_source/frame_{i:04d}.png' for i in range(3)],
                     'minimum_cycle': {'start': 1, 'length': 1},
                     'dirty_cycle': {'start': 2, 'length': 1, 'dirty': True}}
        self.cache = RotationCache(self.root, repo=self.repo)
        self.calls = []

    def tearDown(self):
        target = self.repo.resolve()
        if not target.is_relative_to(self.build) or not target.name.startswith('rotation_'):
            raise RuntimeError('Unexpected cleanup path')
        shutil.rmtree(target)

    def render(self, command, **kwargs):
        self.calls.append(command)
        out = Path(command[command.index('--output')+1])
        timeline = json.loads((out/'timeline.json').read_text())
        times = timeline['source_times']
        for i in range(len(times)):
            Image.new('RGBA', (16, 16), ('blue', 'green', 'yellow')[i % 3]).save(out/f'frame_{i:04d}.png')
        Image.new('RGB', (16, 16), 'blue').save(out/'preview.gif')
        (out/'preview-manifest.json').write_text(json.dumps({'sample_source_times': times}))
        return type('Result', (), {'returncode': 0})()

    def test_results_light_archive_invalidates_clap_and_victory_caches(self):
        archive = self.repo/'orig/GALE01/files/GmRst.usd'
        report_path = self.repo/'build/melee_anim/motions.json'
        report = json.loads(report_path.read_text())
        report['taunts'] = [{'fighter_kind':0,'animation_file':'fake.dat',
                             'standard_facing':{'right':{'source_fighter_kind':0}}}]
        report_path.write_text(json.dumps(report))
        for action in ('results-clap_source','victory1_source','victory1_wait','taunt_source'):
            clip = {**self.clip,'action_key':action}
            archive.write_bytes(b'original scene light bytes')
            before = self.cache._inputs(clip,(0,25,0),False)[0]
            archive.write_bytes(b'replacement scene light bytes')
            after = self.cache._inputs(clip,(0,25,0),False)[0]
            self.assertNotEqual(before,after)

    def test_resume_hashes_timeline_and_resources_and_recovers_corruption(self):
        with patch('tools.melee_anim.rotations.subprocess.run', side_effect=self.render):
            self.assertIs(self.cache.get(self.clip, (0, 0, 0)), self.clip)
            first = self.cache.get(self.clip, (20, 45, 10))
            self.assertEqual(self.cache.get(self.clip, (20, 45, 10)), first)
            self.assertEqual(len(self.calls), 1)
            self.assertEqual(self.calls[0][self.calls[0].index('--size')+1],'1024')
            self.assertIn('--pitch', self.calls[0]); self.assertIn('--samples', self.calls[0])
            self.assertEqual(json.loads((self.root/Path(first['gif']).parent/'preview-manifest.json').read_text())['sample_source_times'], [0, 1, 2])
            (self.root/first['frames'][1]).write_bytes(b'corrupt')
            self.cache.get(self.clip, (20, 45, 10))
            self.assertEqual(len(self.calls), 2)
            Image.new('RGBA', (8, 8), 'green').save(self.model.parent/'color.png')
            changed = self.cache.get(self.clip, (20, 45, 10))
            self.assertNotEqual(changed['gif'], first['gif'])
            self.assertEqual(len(self.calls), 3)
            self.assertNotEqual(self.cache.get(self.clip, (20, 90, 10))['gif'], changed['gif'])

    def test_prepared_lazy_attack_rotates_using_its_render_manifest(self):
        actor={'fighter_kind':0,'animation_file':'fake.dat'}
        catalog={'characters':[{'fighter_kind':0,'actions':[{'key':'attack-62_source','available':True,'actors':[actor]}]}]}
        (self.root/'attack-catalog.json').write_text(json.dumps(catalog))
        clip={**self.clip,'action_key':'attack-62_source','lazy':True}
        with patch('tools.melee_anim.rotations.subprocess.run',side_effect=self.render):
            rotated=self.cache.get(clip,(0,43,0))
            self.assertEqual(len(rotated['frames']),3)
            self.assertEqual(json.loads((self.root/Path(rotated['gif']).parent/'timeline.json').read_text())['source_times'],[0,1,2])
            self.assertEqual(self.cache.get(clip,(0,43,0)),rotated)
            self.assertEqual(len(self.calls),1)

    def test_kirby_power_renders_at_zero_angle_and_separates_cache_and_names(self):
        model=self.repo/'build/melee_anim/exported/kirby/costume_00/model.json'
        model.parent.mkdir(parents=True)
        model.write_text(json.dumps({'fighter_kind':4,'materials':[]}))
        (self.repo/'build/melee_anim/motions.json').write_text(json.dumps({'results':[{'fighter_kind':4,'results_archive':'fake.dat'}]}))
        files=self.repo/'orig/GALE01/files'
        (files/'PlCo.dat').write_bytes(b'synthetic common data fingerprint')
        (files/'hat.dat').write_bytes(b'synthetic hat fingerprint')
        appearance=self.repo/'appearance/model.json';appearance.parent.mkdir()
        appearance.write_text(json.dumps({'materials':[]}))
        clip={**self.clip,'character':'kirby'}
        with patch('tools.melee_anim.kirby_powers.model_for_power',return_value=(appearance,{'archive':files/'hat.dat','body':None})), patch('tools.melee_anim.rotations.subprocess.run',side_effect=self.render):
            first=self.cache.get(clip,(0,0,0),power='mario')
            self.assertEqual(self.cache.get(clip,(0,0,0),power='mario'),first)
            self.assertEqual(len(self.calls),1)
            self.assertEqual(self.calls[0][self.calls[0].index('--kirby-power')+1],'mario')
            self.assertIn('-power-mario.gif',first['download_name'])
            other=self.cache.get(clip,(0,0,0),power='luigi')
            self.assertNotEqual(first['gif'],other['gif'])
            self.assertIs(self.cache.get(clip,(0,0,0)),clip)
            self.assertNotIn('kirby_power',clip)
            with self.assertRaises(ValueError):self.cache.get(self.clip,(0,0,0),power='mario')

    def test_selected_intervals_stills_bundles_and_invalid_input_before_render(self):
        catalog = DownloadCatalog(self.root, clips=[self.clip])
        catalog.rotations = self.cache
        options = dict(character='synthetic', action='results-clap_source', yaw=90)
        with patch('tools.melee_anim.rotations.subprocess.run', side_effect=self.render):
            for mode, color in [('full', (0, 0, 255)), ('minimum', (0, 128, 0)), ('dirty', (255, 255, 0))]:
                frames = catalog.preview(**options, cycle=mode)['frames']
                target, name, _ = catalog.export(**options, cycle=mode, kind='png', size=128)
                self.assertIn('view-x0-y90-z0', name)
                with Image.open(target) as im:
                    self.assertEqual(im.convert('RGB').getpixel((0, 0)), color)
                with Image.open(self.root/frames[0]) as im:
                    self.assertEqual(im.convert('RGB').getpixel((0, 0)), color)
            self.assertEqual(len(self.calls), 1, 'all intervals share rotated full-clip masters')
            target, name, _ = catalog.export(**options, scope='colors', kind='png', frame=2, size=512)
            self.assertIn('view-x0-y90-z0', name)
            with ZipFile(target) as bundle:
                self.assertEqual(len(bundle.namelist()), 1)
                with Image.open(BytesIO(bundle.read(bundle.namelist()[0]))) as im:
                    self.assertEqual(im.size, (512, 512))
                    self.assertEqual(im.convert('RGB').getpixel((0, 0)), (255, 255, 0))
            for changes in [dict(frame=99), dict(character='../../'), dict(yaw=float('nan')), dict(cycle='sync')]:
                with self.assertRaises(ValueError):
                    catalog.export(**{**options, **changes}, kind='png')
            self.assertEqual(len(self.calls), 1)

    def test_sync_and_companion_have_separate_provenance_and_timeline(self):
        sync = self.root/'sync/synthetic'
        sync.mkdir(parents=True)
        plan = {'source_times': [.5, 1.5, .5], 'fit_source_times': [0, 1, 2], 'fps': 50}
        (sync/'preview-manifest.json').write_text(json.dumps({'sample_source_times': plan['source_times'], 'fps': 50, 'sync_plan': plan}))
        self.clip['sync_cycle'] = {'gif': 'sync/synthetic/preview.gif', 'frames': ['unused']*3, 'fps': 50}
        companion = self.model.parent/'companion'
        companion.mkdir()
        (companion/'model.json').write_bytes(self.model.read_bytes())
        (companion/'color.png').write_bytes((self.model.parent/'color.png').read_bytes())
        with patch('tools.melee_anim.rotations.subprocess.run', side_effect=self.render):
            synced = self.cache.get(self.clip, (0, 90, 0), sync=True)
            self.assertIn('--companion', self.calls[0]); self.assertIn('--timeline', self.calls[0])
            original = self.cache.get(self.clip, (0, 90, 0))
            self.assertNotEqual(original['gif'], synced['sync_cycle']['gif'])
            (companion/'model.json').write_text((companion/'model.json').read_text()+' ')
            self.assertNotEqual(self.cache.get(self.clip, (0, 90, 0), sync=True)['sync_cycle']['gif'], synced['sync_cycle']['gif'])

    def test_http_rotation_preview_and_bad_camera_queries(self):
        catalog = DownloadCatalog(self.root, clips=[self.clip]); catalog.rotations = self.cache
        server = make_server(self.root, port=0, catalog=catalog)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        with patch('tools.melee_anim.rotations.subprocess.run', side_effect=self.render):
            try:
                with urlopen(base+'/rotation?character=synthetic&action=results-clap_source&yaw=90&cycle=minimum') as response:
                    result = json.load(response)
                    self.assertEqual(result['angles'], [0, 90, 0]); self.assertEqual(len(result['frames']), 1)
                with urlopen(base+'/export?character=synthetic&action=results-clap_source&yaw=90&kind=png') as response:
                    self.assertIn('view-x0-y90-z0', response.headers['Content-Disposition'])
                for query in ['yaw=nan', 'pitch=181', 'yaw=90&yaw=45', 'frame=0', 'character=../../']:
                    with self.assertRaises(HTTPError) as error:
                        urlopen(base+'/rotation?character=synthetic&action=results-clap_source&'+query)
                    self.assertEqual(error.exception.code, 400)
            finally:
                server.shutdown(); server.server_close(); thread.join()
