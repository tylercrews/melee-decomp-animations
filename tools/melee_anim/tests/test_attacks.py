"""Attack identity/cache checks with synthetic data, never game fixtures."""
from io import BytesIO
import json
from pathlib import Path
import shutil
import unittest
import uuid
from unittest.mock import patch

from PIL import Image

from tools.melee_anim.attacks import AttackCache, attack_label, find_action, sample_times, virtual_clips
from tools.melee_anim.downloads import DownloadCatalog


class AttackTests(unittest.TestCase):
    def test_classification_labels_variants_and_excludes_victim_motions(self):
        self.assertEqual(attack_label('AttackS4Hi')[0], 'Forward smash — high')
        self.assertEqual(attack_label('AttackAirLw')[0], 'Down air')
        self.assertEqual(attack_label('SpecialSAir')[0], 'Side special — aerial')
        self.assertEqual(attack_label('SpecialAirNStart')[0], 'Neutral special — aerial — start')
        self.assertIn('Mario', attack_label('MrSpecialN')[0])
        self.assertIn('Z-air', attack_label('AirCatch')[0])
        self.assertIsNone(attack_label('TKirbyThrowF'))
        self.assertIsNone(attack_label('CaptureDamageHi'))
        self.assertIsNone(attack_label('FallSpecial'))
        self.assertIsNone(attack_label('ItemScrewDamage'))

    def test_half_open_loop_and_terminal_one_shot_grid(self):
        self.assertEqual(len(sample_times(18, True)), 15)
        for i, value in enumerate(sample_times(18, True)):
            self.assertAlmostEqual(value, i*1.2)
        self.assertEqual(sample_times(18, False)[-1], 18)
        self.assertEqual(len(sample_times(18, False)), 16)

    def setUp(self):
        self.base = Path('build/melee_anim_tests').resolve()
        self.repo = self.base/f'attacks_{uuid.uuid4().hex}'
        self.root = self.repo/'build/melee_anim/preview'; self.root.mkdir(parents=True)
        self.model = self.repo/'build/melee_anim/exported/game-and-watch/costume_00/model.json'
        self.model.parent.mkdir(parents=True)
        self.model.write_text(json.dumps({'fighter_kind':24,'materials':[]}))
        (self.repo/'build/melee_anim/motions.json').write_text('{}')
        files = self.repo/'orig/GALE01/files'; files.mkdir(parents=True); (files/'dummy.dat').write_bytes(b'dummy')
        self.actor = {'fighter_kind':24,'animation_file':'dummy.dat','clip':{'frames':2.4,'effective_loop':False,'symbol':'Synthetic'}}
        self.catalog = {'characters':[{'character':'game-and-watch','character_label':'Mr. Game & Watch','fighter_kind':24,
            'costumes':[{'costume_id':i,'file':'shared.dat'} for i in range(4)],
            'actions':[{'key':'attack-62_source','label':'Forward smash','available':True,'actors':[self.actor]}]}]}
        (self.root/'attack-catalog.json').write_text(json.dumps(self.catalog))
        self.clip = virtual_clips(self.root)[0]
        self.cache = AttackCache(self.root,self.repo)
        self.calls = []

    def tearDown(self):
        target = self.repo.resolve()
        if not target.is_relative_to(self.base) or not target.name.startswith('attacks_'):
            raise RuntimeError('Refusing unexpected test cleanup')
        shutil.rmtree(target)

    def render(self, command, **kwargs):
        self.calls.append(command)
        folder = Path(command[command.index('--output')+1]); folder.mkdir(parents=True,exist_ok=True)
        images = []
        for i in range(self.clip['frame_count']):
            image = Image.new('RGB',(256,256),(i*50,10,30)); image.save(folder/f'frame_{i:04d}.png'); images.append(image)
        images[0].save(folder/'preview.gif',save_all=True,append_images=images[1:],duration=20)
        (folder/'preview-manifest.json').write_text(json.dumps({'sample_source_times':sample_times(2.4,False)}))
        return type('Result',(),{'returncode':0})()

    def test_shared_file_preserves_four_actual_costumes_and_no_eager_frames(self):
        clips = virtual_clips(self.root)
        self.assertEqual([c['costume_id'] for c in clips], [0,1,2,3])
        self.assertEqual([c['costume_label'] for c in clips], ['Black','Red','Blue','Green'])
        self.assertTrue(all(c['frames']==[] and c['frame_count']==3 for c in clips))
        self.assertEqual(find_action(self.catalog,24,'attack-62'),self.actor)
        with self.assertRaises(ValueError): find_action(self.catalog,24,'attack-99')

    def test_atomic_cache_reuses_hashes_and_repairs_corrupt_frames(self):
        with patch('tools.melee_anim.attacks.subprocess.run',side_effect=self.render):
            first = self.cache.get(self.clip)
            self.assertEqual(first,self.cache.get(self.clip)); self.assertEqual(len(self.calls),1)
            (self.root/first['frames'][1]).write_bytes(b'broken')
            self.cache.get(self.clip); self.assertEqual(len(self.calls),2)
            self.model.write_text(json.dumps({'fighter_kind':24,'materials':[],'changed':True}))
            second = self.cache.get(self.clip)
            self.assertNotEqual(first['gif'],second['gif']); self.assertEqual(len(self.calls),3)
            self.assertIn('--attack-catalog',self.calls[0])

    def test_virtual_preview_export_and_invalid_frame_before_render(self):
        catalog = DownloadCatalog(self.root,clips=[self.clip]); catalog.attacks=self.cache
        options = dict(character='game-and-watch',action='attack-62_source')
        with patch('tools.melee_anim.attacks.subprocess.run',side_effect=self.render):
            with self.assertRaises(ValueError):catalog.export(**options,kind='png',frame=99)
            self.assertEqual(self.calls,[])
            preview = catalog.preview(**options)
            self.assertEqual(len(preview['frames']),3)
            self.assertEqual(preview['source_times'],sample_times(2.4,False))
            target,_,_ = catalog.export(**options,kind='png',frame=1)
            self.assertEqual(target.read_bytes(),(self.root/preview['frames'][1]).read_bytes())
            self.assertEqual(len(self.calls),1)

    def test_tech_effect_toggle_has_separate_cache_and_names_without_mutation(self):
        action=self.catalog['characters'][0]['actions'][0]
        action.update(key='tech-199_source',animation_type='tech',ground_effect='tech')
        (self.repo/'orig/GALE01/files/EfCoData.dat').write_bytes(b'synthetic effect archive fingerprint')
        (self.repo/'orig/GALE01/files/PlCo.dat').write_bytes(b'synthetic color archive fingerprint')
        (self.root/'attack-catalog.json').write_text(json.dumps(self.catalog))
        self.clip=virtual_clips(self.root)[0]
        self.assertEqual(self.clip['animation_type'],'tech')
        self.assertEqual(self.clip['ground_effect'],'tech')
        with patch('tools.melee_anim.attacks.subprocess.run',side_effect=self.render):
            off=self.cache.get(self.clip,effects=False)
            on=self.cache.get(self.clip,effects=True)
            self.assertNotEqual(on['gif'],off['gif'])
            self.assertIn('-ground-effects.gif',on['download_name'])
            self.assertNotIn('ground-effects',off['download_name'])
            self.assertNotIn('ground-effects',self.clip['download_name'])
            self.assertEqual(self.cache.get(self.clip,effects=True),on)
            self.assertEqual(len(self.calls),2)
            self.assertEqual(self.calls[0][self.calls[0].index('--ground-effects')+1],'off')
            self.assertEqual(self.calls[1][self.calls[1].index('--ground-effects')+1],'on')
            catalog=DownloadCatalog(self.root,clips=[self.clip]);catalog.attacks=self.cache
            with self.assertRaises(ValueError):catalog.preview(character='game-and-watch',action='tech-199_source',effects='invalid')
            with self.assertRaises(ValueError):catalog.export(character='game-and-watch',action='tech-199_source',effects='on',scope='all')
            self.assertEqual(len(catalog.preview(character='game-and-watch',action='tech-199_source',effects='on')['frames']),3)


if __name__=='__main__':unittest.main()
