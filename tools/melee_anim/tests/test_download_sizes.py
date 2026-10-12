from io import BytesIO
import json
from pathlib import Path
import shutil
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
import uuid
from zipfile import ZipFile

from PIL import Image
from tools.melee_anim.downloads import DownloadCatalog, SIZES, resize_gif, resize_png
from tools.melee_anim.player_server import make_server


class DownloadSizeTests(unittest.TestCase):
    def setUp(self):
        self.build = Path('build/melee_anim_tests').resolve()
        self.root = self.build/f'sizes_{uuid.uuid4().hex}'
        self.root.mkdir(parents=True)
        palette = [0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255]+[0]*756
        frames = []
        for color in (1, 2, 3):
            im = Image.new('P', (16, 16), color)
            im.putpalette(palette)
            frames.append(im)
        self.gif = BytesIO()
        frames[0].save(self.gif, format='GIF', save_all=True, append_images=frames[1:],
                       duration=[20, 40, 60], loop=0, disposal=2, optimize=False)
        self.clips = []
        for costume, color in [(0, (255, 0, 0, 255)), (1, (0, 0, 255, 128))]:
            folder = self.root/f'costume_{costume}'
            folder.mkdir()
            (folder/'preview.gif').write_bytes(self.gif.getvalue())
            for index in range(2):
                Image.new('RGBA', (16, 16), color if index else (0, 255, 0, 255)).save(folder/f'frame_{index}.png')
            self.clips.append({'character': 'synthetic', 'action_key': 'taunt_source', 'costume_id': costume,
                               'download_name': f'synthetic-taunt-costume-{costume}.gif',
                               'gif': f'costume_{costume}/preview.gif',
                               'frames': [f'costume_{costume}/frame_{i}.png' for i in range(2)]})
        self.catalog = DownloadCatalog(self.root, self.clips)

    def tearDown(self):
        target = self.root.resolve()
        if not target.is_relative_to(self.build) or not target.name.startswith('sizes_'):
            raise RuntimeError('Unexpected cleanup path')
        shutil.rmtree(target)

    def test_png_sizes_preserve_rgba_and_gif_sizes_preserve_timing_loop_colors(self):
        data = (self.root/'costume_1/frame_1.png').read_bytes()
        for size in SIZES:
            with Image.open(BytesIO(resize_png(data, size))) as im:
                self.assertEqual(im.size, (size, size))
                self.assertEqual(im.getpixel((size//2, size//2)), (0, 0, 255, 128))
            with Image.open(BytesIO(resize_gif(self.gif.getvalue(), size))) as im:
                self.assertEqual(im.size, (size, size))
                self.assertEqual(im.info['loop'], 0)
                for i, (delay, color) in enumerate(zip([20, 40, 60], [(255, 0, 0), (0, 255, 0), (0, 0, 255)])):
                    im.seek(i)
                    self.assertEqual(im.info['duration'], delay)
                    self.assertEqual(im.convert('RGB').getpixel((size//2, size//2)), color)
        # A one-shot stays a one-shot, independently of the preview checkbox.
        im = Image.new('RGB', (16, 16), 'red')
        out = BytesIO(); im.save(out, format='GIF', duration=40)
        with Image.open(BytesIO(resize_gif(out.getvalue(), 128))) as im:
            self.assertNotIn('loop', im.info)

    def test_all_color_stills_keep_the_exact_index_and_changed_source_invalidates_cache(self):
        options = dict(character='synthetic', action='taunt_source', size=512, kind='png', scope='colors', frame=1)
        path, name, mime = self.catalog.export(**options)
        self.assertTrue(name.endswith('-frame-0002-all-colors-512px.zip'))
        self.assertEqual(mime, 'application/zip')
        with ZipFile(path) as archive:
            self.assertEqual(len(archive.namelist()), 2)
            for i, name in enumerate(archive.namelist()):
                self.assertIn('-frame-0002-512px.png', name)
                with Image.open(BytesIO(archive.read(name))) as im:
                    self.assertEqual(im.size, (512, 512))
                    self.assertEqual(im.getpixel((0, 0)), (255, 0, 0, 255) if i == 0 else (0, 0, 255, 128))
        self.assertEqual(self.catalog.export(**options)[0], path)
        Image.new('RGBA', (16, 16), 'white').save(self.root/'costume_0/frame_1.png')
        self.assertNotEqual(self.catalog.export(**options)[0], path)
        for changes in [dict(size=999), dict(frame=2), dict(character='../../'), dict(scope='all')]:
            with self.assertRaises(ValueError):
                self.catalog.export(**{**options, **changes})

    def test_http_attachment_dimensions_and_rejected_queries(self):
        server = make_server(self.root, port=0, catalog=self.catalog)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base+'/_health') as response:
                self.assertEqual(json.load(response)['sizes'], list(SIZES))
            with urlopen(base+'/export?character=synthetic&action=taunt_source&size=2048&kind=png&frame=1') as response:
                self.assertIn('-frame-0002-2048px.png', response.headers['Content-Disposition'])
                with Image.open(BytesIO(response.read())) as im:
                    self.assertEqual(im.size, (2048, 2048))
            with urlopen(base+'/export?character=synthetic&action=taunt_source&size=2048&kind=gif&scope=colors') as response:
                self.assertIn('-all-colors-2048px.zip', response.headers['Content-Disposition'])
                with ZipFile(BytesIO(response.read())) as archive:
                    self.assertEqual(len(archive.namelist()), 2)
                    for name in archive.namelist():
                        self.assertTrue(name.endswith('-2048px.gif'))
                        with Image.open(BytesIO(archive.read(name))) as im:
                            self.assertEqual(im.size, (2048, 2048))
                            self.assertEqual(im.n_frames, 3)
                            self.assertEqual(im.info['loop'], 0)
            with self.assertRaises(HTTPError) as error:
                urlopen(base+'/export?size=123&character=synthetic&action=taunt_source')
            self.assertEqual(error.exception.code, 400)
            with self.assertRaises(HTTPError):
                urlopen(base+'/export?character=synthetic&action=taunt_source&size=128&size=512')
            with urlopen(base+'/export?character=synthetic&action=taunt_source&size=128&kind=gif&view=1') as response:
                self.assertTrue(response.headers['Content-Disposition'].startswith('inline;'))
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_minimum_cycle_gif_and_stills_use_the_same_selected_interval(self):
        for clip in self.clips:
            clip.update(action_key='results-clap_source', fps=50,
                        minimum_cycle={'start': 1, 'length': 1, 'full_length': 2})
        options = dict(character='synthetic', action='results-clap_source', size=128, cycle='minimum')
        path, name, _ = self.catalog.export(**options)
        self.assertIn('-minimum-cycle-128px.gif', name)
        with Image.open(path) as im:
            self.assertEqual(im.info['loop'], 0)
            self.assertEqual(im.info['duration'], 20)
            self.assertEqual(im.n_frames, 1)
            self.assertEqual(im.convert('RGB').getpixel((0, 0)), (255, 0, 0))
        path, name, _ = self.catalog.export(**options, kind='png', frame=0)
        with Image.open(path) as im:
            self.assertEqual(im.getpixel((0, 0)), (255, 0, 0, 255))
        self.assertIn('-minimum-cycle-frame-0001-128px.png', name)
        with self.assertRaises(ValueError):
            self.catalog.export(**options, kind='png', frame=1)
        path, _, _ = self.catalog.export(**options, scope='colors')
        with ZipFile(path) as archive:
            self.assertEqual(len(archive.namelist()), 2)
            self.assertTrue(all('minimum-cycle' in name for name in archive.namelist()))
        full, _, _ = self.catalog.export(**{**options, 'cycle': 'full'})
        with Image.open(full) as im:
            self.assertEqual(im.n_frames, 3)
        with self.assertRaises(ValueError):
            self.catalog.export(**{**options, 'cycle': 'invalid'})

    def test_dirty_loop_uses_its_own_interval_names_and_clean_aggregate_fallback(self):
        for clip in self.clips:
            clip.update(action_key='results-clap_source', fps=50,
                        minimum_cycle={'start': 0, 'length': 1, 'full_length': 2})
        self.clips[0]['dirty_cycle'] = {'start': 1, 'length': 1, 'full_length': 2, 'dirty': True}
        options = dict(character='synthetic', action='results-clap_source', size=128, cycle='dirty')
        path, name, _ = self.catalog.export(**options, kind='png')
        self.assertIn('-dirty-loop-frame-0001-128px.png', name)
        with Image.open(path) as im:
            self.assertEqual(im.getpixel((0, 0)), (255, 0, 0, 255))
        path, name, _ = self.catalog.export(**options, scope='all')
        self.assertIn('-dirty-loop-128px.zip', name)
        with ZipFile(path) as archive:
            self.assertTrue(any('dirty-loop' in n for n in archive.namelist()))
            self.assertTrue(any('minimum-cycle' in n for n in archive.namelist()))
            for n in archive.namelist():
                with Image.open(BytesIO(archive.read(n))) as im:
                    self.assertEqual(im.info['loop'], 0)
                    self.assertEqual(im.info['duration'], 20)

    def test_sync_uses_rendered_frames_and_exports_only_claps_in_the_all_bundle(self):
        for clip in self.clips:
            clip.update(action_key='results-clap_source', fps=50,
                        sync_cycle={'gif': clip['gif'], 'frames': list(reversed(clip['frames'])), 'fps': 50})
        taunt = {**self.clips[0], 'action_key': 'taunt_source', 'download_name': 'taunt.gif'}
        self.catalog.clips.append(taunt)
        options = dict(character='synthetic', action='results-clap_source', cycle='sync', size=128)
        path, name, _ = self.catalog.export(**options, kind='png')
        self.assertIn('-clapping-sync-frame-0001-128px.png', name)
        with Image.open(path) as im:
            self.assertEqual(im.getpixel((0, 0)), (255, 0, 0, 255))
        path, name, _ = self.catalog.export(**options, scope='all')
        self.assertIn('melee-all-characters-clapping-sync-128px.zip', name)
        with ZipFile(path) as archive:
            self.assertEqual(len(archive.namelist()), 2)
            self.assertTrue(all('clapping-sync' in n for n in archive.namelist()))
        with self.assertRaises(ValueError):
            self.catalog.export(**{**options, 'action': 'taunt_source'})
        del self.clips[0]['sync_cycle']
        with self.assertRaises(ValueError):
            self.catalog.export(**options)


if __name__ == '__main__':
    unittest.main()
