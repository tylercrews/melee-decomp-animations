from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid
from zipfile import ZipFile

from PIL import Image
from tools.melee_anim.downloads import DownloadCatalog
from tools.melee_anim.hd_stills import HDArtifacts, StillCache, crop_transparent_png
from tools.melee_anim.player_server import make_server


class StillCacheTests(unittest.TestCase):
    def setUp(self):
        self.build=Path('build/melee_anim_tests').resolve()
        self.repo=self.build/f'hd_{uuid.uuid4().hex}'
        self.root=self.repo/'build/melee_anim/preview'
        folder=self.root/'synthetic/costume_00/results-clap_source'
        folder.mkdir(parents=True)
        self.model=self.repo/'build/melee_anim/exported/synthetic/costume_00/model.json'
        self.model.parent.mkdir(parents=True)
        self.model.write_text(json.dumps({'fighter_kind':0,'materials':[{'textures':[{'image_file':'color.png'}]}]}))
        Image.new('RGBA',(8,8),'blue').save(self.model.parent/'color.png')
        files=self.repo/'orig/GALE01/files';files.mkdir(parents=True)
        (files/'fake.dat').write_bytes(b'synthetic source')
        (self.repo/'build/melee_anim/motions.json').write_text(json.dumps({'results':[{'fighter_kind':0,'results_archive':'fake.dat'}]}))
        self.times=[0,1.2,2.4,3.6]
        (folder/'preview-manifest.json').write_text(json.dumps({'sample_source_times':self.times,'fps':50}))
        self.clip={'character':'synthetic','action_key':'results-clap_source','costume_id':0,
                   'gif':'synthetic/costume_00/results-clap_source/preview.gif',
                   'minimum_cycle':{'start':1,'length':2},'dirty_cycle':{'start':2,'length':1,'dirty':True}}
        self.cache=StillCache(self.root,self.repo/'temporary-renders',repo=self.repo)
        self.calls=[]

    def tearDown(self):
        target=self.repo.resolve()
        if not target.is_relative_to(self.build) or not target.name.startswith('hd_'):raise RuntimeError('Unexpected cleanup path')
        shutil.rmtree(target)

    def render(self,command,**kwargs):
        self.calls.append(command)
        out=Path(command[command.index('--output')+1])
        timeline=json.loads((out/'timeline.json').read_text())
        index=int(command[command.index('--still-frame')+1]);size=int(command[command.index('--size')+1])
        times=timeline.get('source_times',[])
        Image.new('RGBA',(size,size),(40,index,80,128)).save(out/'frame_0000.png')
        (out/'preview-manifest.json').write_text(json.dumps({'sample_source_times':[times[index]],'complete_interval':False,'size':size}))
        return type('Result',(),{'returncode':0})()

    def test_exact_fractional_frame_whole_clip_samples_cache_and_corruption(self):
        with patch('tools.melee_anim.hd_stills.subprocess.run',side_effect=self.render):
            target,key=self.cache.get(self.clip,(20,43,10),2048,frame=2)
            self.assertEqual(self.cache.get(self.clip,(20,43,10),2048,frame=2),(target,key))
            self.assertEqual(len(self.calls),1)
            settings=json.loads((target.parent/'timeline.json').read_text())
            self.assertEqual(settings['source_times'],self.times)
            self.assertEqual(settings['fit_source_times'],self.times)
            self.assertEqual(json.loads((target.parent/'preview-manifest.json').read_text())['sample_source_times'],[2.4])
            self.assertEqual(list(target.parent.glob('frame_*.png')),[target])
            self.assertFalse((target.parent/'preview.gif').exists())
            self.assertIn('--still-frame',self.calls[0]);self.assertIn('43',self.calls[0])
            target.write_bytes(b'corrupt')
            self.cache.get(self.clip,(20,43,10),2048,frame=2)
            self.assertEqual(len(self.calls),2)
            Image.new('RGBA',(8,8),'red').save(self.model.parent/'color.png')
            self.assertNotEqual(self.cache.get(self.clip,(20,43,10),2048,frame=2)[1],key)

    def test_short_cycles_use_source_offsets_and_frame_changes_invalidate(self):
        with patch('tools.melee_anim.hd_stills.subprocess.run',side_effect=self.render):
            minimum,key=self.cache.get(self.clip,(0,0,0),2048,frame=1,cycle='minimum')
            dirty,other=self.cache.get(self.clip,(0,0,0),2048,frame=0,cycle='dirty')
            self.assertEqual(key,other,'same source pose reuses the native PNG across cut labels')
            self.assertEqual(json.loads((minimum.parent/'preview-manifest.json').read_text())['sample_source_times'],[2.4])
            self.assertNotEqual(self.cache.get(self.clip,(0,0,0),2048,frame=0)[1],key)
            for opts in (dict(frame=-1),dict(frame=4),dict(size=512)):
                with self.assertRaises(ValueError):self.cache.get(self.clip,(0,0,0),**{'size':2048,**opts})

    def test_unprepared_lazy_hd_frame_uses_catalog_provenance_without_a_gif(self):
        actor={'fighter_kind':0,'animation_file':'fake.dat'}
        catalog={'characters':[{'fighter_kind':0,'actions':[{'key':'attack-62_source','available':True,'actors':[actor]}]}]}
        (self.root/'attack-catalog.json').write_text(json.dumps(catalog))
        clip={**self.clip,'action_key':'attack-62_source','lazy':True,'gif':'','period':2.4,'authored_loop':False,'fps':50}
        with patch('tools.melee_anim.hd_stills.subprocess.run',side_effect=self.render):
            target,_=self.cache.get(clip,(0,43,0),2048,frame=1)
            self.assertEqual(json.loads((target.parent/'preview-manifest.json').read_text())['sample_source_times'],[1.2])
            self.assertFalse((target.parent/'preview.gif').exists())

    def test_sync_preserves_the_full_authored_fractional_plan(self):
        folder=self.root/'sync';folder.mkdir()
        plan={'source_times':[.25,.75],'fit_source_times':self.times,'length':2,'fps':50}
        (folder/'preview-manifest.json').write_text(json.dumps({'sample_source_times':[.25,.75],'fps':50,'sync_plan':plan}))
        clip={**self.clip,'sync_cycle':{'gif':'sync/preview.gif'}}
        def sync_render(command,**kwargs):
            out=Path(command[command.index('--output')+1]);timeline=json.loads((out/'timeline.json').read_text())
            self.assertEqual(timeline,plan);self.assertIn('--timeline',command)
            Image.new('RGBA',(2048,2048),'blue').save(out/'frame_0000.png')
            (out/'preview-manifest.json').write_text(json.dumps({'sample_source_times':[.75],'complete_interval':False,'size':2048}))
            return type('Result',(),{'returncode':0})()
        with patch('tools.melee_anim.hd_stills.subprocess.run',side_effect=sync_render):
            self.cache.get(clip,(0,0,0),2048,frame=1,cycle='sync')


class HDArtifactTests(unittest.TestCase):
    def test_crop_preserves_exact_rgba_black_and_faint_pixels_and_repairs_cache(self):
        artifacts=HDArtifacts()
        try:
            folder=artifacts.root/'renders/example';folder.mkdir(parents=True)
            source=folder/'frame.png'
            image=Image.new('RGBA',(9,8),(90,120,200,0))
            image.putpixel((2,1),(0,0,0,255));image.putpixel((6,5),(255,180,60,1))
            image.save(source)
            cropped,key=crop_transparent_png(source,'source-key')
            with Image.open(cropped) as result:
                self.assertEqual(result.size,(5,5))
                self.assertEqual(result.tobytes(),image.crop((2,1,7,6)).tobytes())
                self.assertEqual(result.getpixel((4,4))[3],1)
                self.assertEqual(result.getpixel((0,0)),(0,0,0,255))
            saved=json.loads((folder/'crop.json').read_text())
            self.assertEqual(saved['bounds'],[2,1,7,6]);self.assertEqual(saved['source_size'],[9,8])
            self.assertEqual(crop_transparent_png(source,'source-key'),(cropped,key))
            cropped.write_bytes(b'corrupt')
            crop_transparent_png(source,'source-key')
            with Image.open(cropped) as result:self.assertEqual(result.size,(5,5))
            with Image.open(source) as full:self.assertEqual(full.size,(9,8),'full canvas remains available when cropping is disabled')
        finally:artifacts.close()

    def test_empty_frame_crop_is_a_valid_one_pixel_transparent_png(self):
        artifacts=HDArtifacts()
        try:
            folder=artifacts.root/'renders/empty';folder.mkdir(parents=True)
            source=folder/'frame.png';Image.new('RGBA',(9,8),(200,90,20,0)).save(source)
            target,_=crop_transparent_png(source,'empty')
            with Image.open(target) as result:
                self.assertEqual(result.size,(1,1));self.assertEqual(result.getpixel((0,0))[3],0)
        finally:artifacts.close()

    def test_temporary_location_expiry_protection_and_cleanup(self):
        artifacts=HDArtifacts(ttl=10)
        try:
            root=artifacts.root
            self.assertFalse(root.is_relative_to(Path.cwd()))
            folder=root/'renders/example';folder.mkdir(parents=True)
            target=folder/'frame.png';Image.new('RGBA',(4,4),'red').save(target)
            url=artifacts.publish(target,'selected.png');token=url.rsplit('/',1)[1]
            self.assertEqual(artifacts.get(token),(target,'selected.png'))
            self.assertIsNone(artifacts.get('../frame.png'))
            expiry=artifacts.records[token][2]
            os.utime(folder,(0,0))
            with patch('tools.melee_anim.hd_stills.time.monotonic',return_value=expiry+1):
                artifacts.begin();artifacts.prune();self.assertTrue(target.exists())
                artifacts.end();self.assertIsNone(artifacts.get(token))
                artifacts.prune();self.assertFalse(folder.exists())
        finally:artifacts.close()
        self.assertFalse(root.exists())


class HDExportTests(unittest.TestCase):
    def setUp(self):
        self.build=Path('build/melee_anim_tests').resolve()
        self.root=self.build/f'hd_export_{uuid.uuid4().hex}';self.root.mkdir(parents=True)
        self.clips=[{'character':'synthetic','character_label':'Synthetic','action_key':'taunt_source','costume_id':i,
                     'costume_label':str(i),'frames':['unused0','unused1'],'download_name':f'synthetic-color-{i}.gif'} for i in (0,1)]
        self.catalog=DownloadCatalog(self.root,self.clips)
        self.calls=[]

    def tearDown(self):
        self.catalog.hd_artifacts.close()
        target=self.root.resolve()
        if not target.is_relative_to(self.build) or not target.name.startswith('hd_export_'):raise RuntimeError('Unexpected cleanup path')
        shutil.rmtree(target)

    def render(self,clip,angles,size,frame,cycle,power,center,effects,electric,progress):
        self.calls.append((clip['costume_id'],angles,size,frame,cycle,power,center,effects,electric))
        folder=self.catalog.hd_artifacts.root/'renders'/str(clip['costume_id']);folder.mkdir(parents=True,exist_ok=True)
        target=folder/'frame.png'
        Image.new('RGBA',(size,size),(clip['costume_id']*100,frame,0,128)).save(target)
        if progress:progress('PNG rendered',1,1)
        return target,str(clip['costume_id'])

    def test_all_colors_native_zip_shared_settings_progress_and_no_project_pngs(self):
        events=[]
        with patch('tools.melee_anim.hd_stills.StillCache.get',side_effect=self.render):
            target,name,mime=self.catalog.export(character='synthetic',action='taunt_source',render='hd',kind='png',scope='colors',frame=1,yaw=43,size=2048,progress=events.append)
        self.assertFalse(target.is_relative_to(self.root));self.assertEqual(mime,'application/zip')
        self.assertIn('-hd-2048px.zip',name)
        self.assertEqual([c[0] for c in self.calls],[0,1]);self.assertTrue(all(c[1:4]==((0.,43.,0.),2048,1) for c in self.calls))
        with ZipFile(target) as archive:
            self.assertEqual(len(archive.namelist()),2)
            for name in archive.namelist():
                with Image.open(BytesIO(archive.read(name))) as image:self.assertEqual(image.size,(2048,2048));self.assertEqual(image.mode,'RGBA')
        self.assertEqual(events[-1]['files_completed'],2)
        self.assertEqual([e['percent'] for e in events],sorted(e['percent'] for e in events))
        self.assertFalse(list(self.root.rglob('*.png')))

    def test_crop_default_all_colors_uses_individual_bounds_and_off_keeps_canvas(self):
        def bordered(clip,angles,size,*args):
            folder=self.catalog.hd_artifacts.root/'renders'/str(clip['costume_id']);folder.mkdir(parents=True,exist_ok=True)
            target=folder/'frame.png';image=Image.new('RGBA',(size,size),(60,80,90,0))
            width,height=(3,2) if clip['costume_id']==0 else (4,3)
            image.paste((0,0,0,255),(17,23,17+width,23+height));image.save(target)
            return target,str(clip['costume_id'])
        opts=dict(character='synthetic',action='taunt_source',render='hd',kind='png',scope='colors',frame=1,size=2048)
        with patch('tools.melee_anim.hd_stills.StillCache.get',side_effect=bordered):
            cropped,name,_=self.catalog.export(**opts)
            full,full_name,_=self.catalog.export(**opts,crop='off')
        self.assertNotEqual(cropped,full);self.assertIn('-cropped-',name);self.assertNotIn('-cropped-',full_name)
        with ZipFile(cropped) as archive:
            for i,name in enumerate(archive.namelist()):
                with Image.open(BytesIO(archive.read(name))) as image:self.assertEqual(image.size,(3,2) if i==0 else (4,3))
        with ZipFile(full) as archive:
            for name in archive.namelist():
                with Image.open(BytesIO(archive.read(name))) as image:self.assertEqual(image.size,(2048,2048))
        with self.assertRaises(ValueError):self.catalog.export(**opts,crop='invalid')

    def test_http_hd_download_is_temporary_attachment_and_errors_are_clean(self):
        server=make_server(self.root,0,catalog=self.catalog)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with patch('tools.melee_anim.hd_stills.StillCache.get',side_effect=self.render):
                with urlopen(base+'/prepare-export?character=synthetic&action=taunt_source&kind=png&render=hd&size=2048&frame=1&progress='+uuid.uuid4().hex) as response:ready=json.load(response)
            self.assertTrue(ready['url'].startswith('/hd-export/'));self.assertEqual(ready['progress']['status'],'complete')
            with urlopen(Request(base+ready['url'],method='HEAD')) as response:self.assertEqual(response.headers['Cache-Control'],'no-store')
            with urlopen(base+ready['url']) as response:
                self.assertTrue(response.headers['Content-Disposition'].startswith('attachment;'))
                with Image.open(BytesIO(response.read())) as image:self.assertEqual(image.size,(2048,2048))
            for query in ('render=hd&kind=gif','render=hd&kind=png&size=512','kind=png&size=4096','render=hd&kind=png&frame=9'):
                with self.assertRaises(HTTPError) as error:urlopen(base+'/prepare-export?character=synthetic&action=taunt_source&'+query)
                self.assertEqual(error.exception.code,400)
            with self.assertRaises(HTTPError) as error:urlopen(base+'/hd-export/../../missing')
            self.assertEqual(error.exception.code,404)
        finally:server.shutdown();server.server_close();thread.join()
