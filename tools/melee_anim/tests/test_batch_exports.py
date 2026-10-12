"""Synthetic batch semantics and ZIP enumeration; no original assets."""
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import unittest
import uuid
import threading
from urllib.request import urlopen
from zipfile import ZipFile
from PIL import Image

from tools.melee_anim.batch_exports import enrich,select_all,family
from tools.melee_anim.downloads import DownloadCatalog
from tools.melee_anim.kirby_powers import powers
from tools.melee_anim.player_server import make_server


def action(aid,label,phase_ids=None,kind='attack',**extra):
    key=f'{kind}-{aid}'+('-combined' if phase_ids else '')+'_source'
    actor={'sequence':{'phases':[{'clip':{'animation_id':i}} for i in phase_ids]}} if phase_ids else {}
    return dict(key=key,animation_id=aid,label=label,animation_type=kind,available=True,actors=[actor],
                sequence={'phases':phase_ids} if phase_ids else None,**extra)


class BatchFamilyTests(unittest.TestCase):
    def test_move_family_uses_labels_not_shared_ids_and_prefers_combined(self):
        mario=[action(100,'Neutral special — grounded — start'),action(101,'Neutral special — grounded — loop'),
               action(102,'Neutral special — grounded — end'),action(100,'Neutral special — grounded — combined',[100,101,102]),
               action(103,'Neutral special — aerial')]
        fox=[action(295,'Neutral special — grounded — combined',[295,296,297]),
             action(296,'Neutral special — grounded — loop'),action(100,'Forward smash')]
        catalog={'characters':[dict(character='mario',actions=mario),dict(character='fox',actions=fox)]}
        clips=enrich([dict(character=slug,action_key=a['key']) for slug,items in [('mario',mario),('fox',fox)] for a in items],catalog)
        chosen,title=select_all(clips,'mario','attack-101_source')
        self.assertEqual(title,'Neutral special')
        self.assertEqual({(c['character'],c['action_key']) for c in chosen},
                         {('mario','attack-100-combined_source'),('mario','attack-103_source'),('fox','attack-295-combined_source')})
        self.assertNotEqual(family(action(108,'Beam Sword — Jab',held_item=dict(name='Beam Sword',item_kind=12,variant=0))),
                            family(action(112,'Home-Run Bat — Jab',held_item=dict(name='Home-Run Bat',item_kind=11,variant=0))))
        self.assertNotEqual(family(action(400,'Kirby copy: Fox — Neutral special — grounded')),
                            family(action(295,'Neutral special — grounded')))

    def test_cross_family_lying_motion_is_not_hidden_by_missed_tech_sequence(self):
        parts=[action(183,'Missed tech — face up',kind='tech'),action(184,'Lying on ground — face up',kind='tech'),
               action(183,'Missed tech — face up → lying on ground',[183,184],kind='tech')]
        clips=enrich([dict(character='mario',action_key=a['key']) for a in parts],{'characters':[dict(character='mario',actions=parts)]})
        chosen,_=select_all(clips,'mario','tech-184_source')
        self.assertEqual([c['action_key'] for c in chosen],['tech-184_source'])


class BatchZipTests(unittest.TestCase):
    def setUp(self):
        self.build=Path('build/melee_anim_tests').resolve();self.root=self.build/f'batches_{uuid.uuid4().hex}'
        self.root.mkdir(parents=True);self.clips=[];self.calls=[]
        keys=[f'victory{i}_{section}' for i in (1,2,3) for section in ('source','wait')]+['taunt_source','results-clap_source']
        for char,count in [('mario',2),('kirby',6)]:
            for cid in range(count):
                for key in keys:
                    folder=self.root/char/str(cid)/key;folder.mkdir(parents=True)
                    image=Image.new('RGBA',(16,16),(cid*30,100,200,255));image.save(folder/'frame.png')
                    image.save(folder/'preview.gif')
                    relative=folder.relative_to(self.root).as_posix()
                    c=dict(character=char,costume_id=cid,action_key=key,download_name=f'{char}-{key}-{cid}.gif',
                           frames=[relative+'/frame.png'],gif=relative+'/preview.gif',fps=50)
                    if key=='results-clap_source':c['sync_cycle']=dict(frames=c['frames'],gif=c['gif'],fps=50)
                    self.clips.append(c)
        self.catalog=DownloadCatalog(self.root,clips=self.clips)
        def rotated(c,angles,**options):
            self.calls.append((c['character'],c['costume_id'],options['power'],options['sync']))
            name=c['download_name']
            if options['power']!='none':name=name.replace('.gif',f'-power-{options["power"]}.gif')
            return {**c,'download_name':name}
        self.catalog.rotations=SimpleNamespace(get=rotated)

    def tearDown(self):
        if not self.root.is_relative_to(self.build):raise RuntimeError('Unexpected cleanup path')
        shutil.rmtree(self.root)

    def test_victory_batch_contains_all_six_choices_and_actual_costumes_only(self):
        path,name,_=self.catalog.export(character='mario',action='victory2_wait',scope='all',size=128)
        with ZipFile(path) as z:
            self.assertEqual(len(z.namelist()),48)
            self.assertTrue(all('victory' in n for n in z.namelist()))
        self.assertIn('victory-poses',name)

    def test_all_hats_adds_25_appearances_per_kirby_color_without_changing_other_fighters(self):
        path,name,_=self.catalog.export(character='mario',action='results-clap_source',scope='all',cycle='sync',hats='all',size=128)
        with ZipFile(path) as z:
            self.assertEqual(len(z.namelist()),2+6*len(powers()))
            self.assertEqual(len(z.namelist()),len(set(z.namelist())))
            for p in powers()[1:]:self.assertEqual(sum('-power-'+p['slug']+'-' in n for n in z.namelist()),6)
        self.assertTrue(all(p=='none' for char,_,p,_ in self.calls if char=='mario'))
        self.assertTrue(all(sync for *_,sync in self.calls))
        self.assertIn('kirby-all-hats-all-colors',name)
        self.assertNotIn('power-',self.clips[0]['download_name'])

    def test_color_stills_include_all_hats_and_bad_options_fail_before_render(self):
        path,name,_=self.catalog.export(character='kirby',action='victory3_source',scope='colors',kind='png',hats='all',power='samus',size=128)
        with ZipFile(path) as z:self.assertEqual(len(z.namelist()),156)
        self.assertIn('kirby-all-hats-all-colors',name);self.assertNotIn('power-samus',name)
        before=len(self.calls)
        for extra in (dict(hats='bad'),dict(hats='all',scope='costume'),dict(hats='all',kind='png',scope='all'),dict(hats='all',kind='png',scope='colors',frame=9)):
            with self.assertRaises(ValueError):self.catalog.export(character='kirby',action='victory3_source',**extra)
        self.assertEqual(len(self.calls),before)

    def test_server_does_not_hold_a_whole_batch_lock_over_other_previews(self):
        started=threading.Event();release=threading.Event();errors=[]
        target=self.root/'ready.zip';target.write_bytes(b'synthetic prepared bundle')
        def export(**options):
            started.set()
            if not release.wait(5):raise RuntimeError('Test batch was not released')
            return target,'ready.zip','application/zip'
        fake=SimpleNamespace(clips=[],export=export,preview=lambda **options:{'frames':['ready.png']})
        server=make_server(self.root,0,catalog=fake);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def batch():
            try:
                with urlopen(base+'/prepare-export?character=synthetic&action=taunt_source',timeout=6) as response:json.load(response)
            except Exception as error:errors.append(error)
        worker=threading.Thread(target=batch);worker.start()
        try:
            self.assertTrue(started.wait(2))
            with urlopen(base+'/rotation?character=synthetic&action=taunt_source',timeout=2) as response:
                self.assertEqual(json.load(response)['frames'],['ready.png'])
        finally:
            release.set();worker.join();server.shutdown();server.server_close();thread.join()
        self.assertEqual(errors,[])


if __name__=='__main__':unittest.main()
