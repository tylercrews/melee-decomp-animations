from io import BytesIO
import json
from pathlib import Path
import shutil
import threading
import unittest
import uuid
from unittest.mock import patch
from urllib.request import urlopen
from urllib.error import HTTPError

from PIL import Image

from tools.melee_anim.downloads import resize_gif
from tools.melee_anim.export_progress import ProgressRegistry, render_progress
from tools.melee_anim.player_server import make_server


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.build = Path('build/melee_anim_tests').resolve()
        self.root = self.build/f'progress_{uuid.uuid4().hex}'
        self.root.mkdir(parents=True)

    def tearDown(self):
        target = self.root.resolve()
        if not target.is_relative_to(self.build) or not target.name.startswith('progress_'):
            raise RuntimeError('Unexpected cleanup path')
        shutil.rmtree(target)

    def test_registry_is_bounded_and_retains_active_jobs_and_snapshots(self):
        jobs = ProgressRegistry(limit=2,ttl=1)
        a,b,c = [uuid.uuid4().hex for _ in range(3)]
        update = jobs.start(a);jobs.start(b)
        update(dict(total=5,completed=2,percent=33))
        copy = jobs.get(a);copy['completed']=99
        self.assertEqual(jobs.get(a)['completed'],2)
        with self.assertRaises(ValueError):jobs.start(a)
        with self.assertRaises(ValueError):jobs.start(c)
        jobs.finish(b,'failed');jobs.start(c)
        self.assertIsNone(jobs.get(b));self.assertEqual(jobs.get(a)['status'],'working')
        jobs.finish(a)
        with patch('tools.melee_anim.export_progress.time.monotonic',return_value=10**20):
            self.assertIsNone(jobs.get(a));self.assertEqual(jobs.get(c)['status'],'working')
        with self.assertRaises(ValueError):jobs.start('../../unsafe')

    def test_resize_reports_real_frame_stages_without_changing_bytes(self):
        images = [Image.new('RGBA',(16,16),color) for color in ('red','blue','green')]
        source=BytesIO();images[0].save(source,format='GIF',save_all=True,append_images=images[1:],duration=[20,40,60],loop=0)
        events=[]
        plain = resize_gif(source.getvalue(),128)
        tracked = resize_gif(source.getvalue(),128,progress=lambda *row:events.append(row))
        self.assertEqual(plain,tracked)
        for phase in ('Resizing frames','Quantizing frames','Encoding frames'):
            self.assertEqual([done for name,done,total in events if name==phase],[1,2,3])
            self.assertTrue(all(total==3 for name,done,total in events if name==phase))

    def test_render_monitor_uses_reported_frames_not_old_frame_files(self):
        log = self.root/'render.log';log.write_text('Preparing pose\n')
        (self.root/'frame_0000.png').write_bytes(b'stale previous frame')
        events=[];seen=threading.Event()
        def report(*event):events.append(event);seen.set()
        with render_progress(log,40,report):
            self.assertTrue(seen.wait(2))
            self.assertEqual(events[0],('Preparing animation',0,40))
            log.write_text('Rendered 20/40 frames (2.0s)\nRendered 40/40 frames (3.0s)\n')
        self.assertEqual(events[-1],('Encoding rendered GIF',40,40))

    def test_http_progress_remains_readable_during_preparation_and_finish(self):
        started,release = threading.Event(),threading.Event()
        target = self.root/'ready.gif';target.write_bytes(b'ready')
        class Catalog:
            clips=[]
            def export(self,progress=None,**options):
                progress(dict(total=3,completed=1,files_completed=0,percent=20,
                              phase='Rendering frames',frames_done=20,frames_total=40))
                started.set();release.wait(5)
                return target,'ready.gif','image/gif'
        server = make_server(self.root,0,catalog=Catalog())
        serving=threading.Thread(target=server.serve_forever,daemon=True);serving.start()
        base=f'http://127.0.0.1:{server.server_port}';key=uuid.uuid4().hex;results=[]
        def prepare():
            with urlopen(base+'/prepare-export?character=synthetic&action=taunt_source&progress='+key,timeout=8) as response:results.append(json.load(response))
        worker=threading.Thread(target=prepare);worker.start()
        try:
            self.assertTrue(started.wait(3))
            with urlopen(base+'/export-progress?id='+key,timeout=2) as response:
                self.assertEqual(response.headers['Cache-Control'],'no-store');state=json.load(response)
            self.assertEqual((state['completed'],state['frames_done'],state['frames_total']),(1,20,40))
            with self.assertRaises(HTTPError) as duplicate:
                urlopen(base+'/prepare-export?progress='+key,timeout=2)
            self.assertEqual(duplicate.exception.code,400)
            with urlopen(base+'/export-progress?id='+key) as response:self.assertEqual(json.load(response)['status'],'working')
            release.set();worker.join(5)
            self.assertEqual(results[0]['progress']['status'],'complete')
            self.assertEqual(results[0]['progress']['percent'],100)
            self.assertEqual(results[0]['url'],'/ready.gif')
            with self.assertRaises(HTTPError) as missing:urlopen(base+'/export-progress?id=unknown')
            self.assertEqual(missing.exception.code,404)
        finally:
            release.set();worker.join(5);server.shutdown();server.server_close();serving.join(3)
