import unittest
import json
from pathlib import Path
import shutil
import uuid
import numpy as np
from tools.melee_anim.cycles import find_minimum_cycle, find_dirty_cycle,preserve_intervals,input_fingerprint


class CycleTests(unittest.TestCase):
    def test_resolution_refresh_retains_cut_and_rejects_changed_source_timing(self):
        build=Path('build/melee_anim_tests').resolve();root=build/f'cycles_{uuid.uuid4().hex}'
        folder=root/'synthetic/costume_00/results-clap_source';folder.mkdir(parents=True)
        manifest=folder/'preview-manifest.json'
        data={'sample_source_times':list(range(20)),'fps':50}
        manifest.write_text(json.dumps(data))
        for i in range(20):(folder/f'frame_{i:04d}.png').write_bytes(b'larger synthetic frame')
        cycle=dict(start=2,length=4,full_length=20,fps=50,source_interval=[2,6],costume_count=1,input_fingerprint='old')
        report=root/'minimum-cycles.json';report.write_text(json.dumps({'characters':{'synthetic':cycle}}))
        try:
            result=preserve_intervals(root)['characters']['synthetic']
            self.assertEqual(result['input_fingerprint'],input_fingerprint([manifest]))
            self.assertEqual(result['source_interval'],[2,6]);self.assertEqual(result['length'],4)
            original=report.read_bytes();data['sample_source_times'][6]=6.5;manifest.write_text(json.dumps(data))
            with self.assertRaises(ValueError):preserve_intervals(root)
            self.assertEqual(report.read_bytes(),original)
        finally:
            if not root.is_relative_to(build):raise RuntimeError('Unexpected cleanup path')
            shutil.rmtree(root)

    def test_finds_smallest_real_repeat_not_a_matching_endpoint(self):
        time = np.arange(120)*2*np.pi/20
        wave = np.column_stack((np.sin(time), np.cos(time)))
        found = find_minimum_cycle(np.stack((wave, wave*.8)))
        self.assertEqual(found['length'], 20)
        self.assertLess(found['start']+found['length'], 120)
        self.assertTrue(found['edited'])

    def test_holds_slow_drift_and_one_shot_do_not_become_short_loops(self):
        self.assertIsNone(find_minimum_cycle(np.ones((2, 100, 3))))
        self.assertIsNone(find_minimum_cycle(np.arange(100)[None, :, None]))
        time = np.arange(100)*2*np.pi/100
        self.assertIsNone(find_minimum_cycle(np.column_stack((np.sin(time), np.cos(time)))[None]))

    def test_every_costume_must_pass_recurrence_and_the_unwrapped_seam(self):
        time = np.arange(120)*2*np.pi/20
        wave = np.column_stack((np.sin(time), np.cos(time)))
        drift = np.column_stack((np.arange(120)*10, np.arange(120)*10))
        self.assertIsNone(find_minimum_cycle(np.stack((wave, drift))))

    def test_dirty_review_labels_failed_checks_without_promoting_the_candidate(self):
        # Repeated hand-like motion with a nonrepeating body drift.
        time = np.arange(100)*2*np.pi/20
        wave = np.column_stack((np.sin(time), np.cos(time), np.arange(100)*.06))
        samples = np.stack((wave, wave*.9))
        self.assertIsNone(find_minimum_cycle(samples))
        dirty = find_dirty_cycle(samples)
        self.assertIsNotNone(dirty)
        self.assertTrue(dirty['dirty'])
        self.assertTrue(dirty['failed_checks'])
        self.assertLess(dirty['length'], 50)

    def test_dirty_review_does_not_make_held_drifting_or_approved_loops_dirty(self):
        self.assertIsNone(find_dirty_cycle(np.ones((1, 100, 3))))
        self.assertIsNone(find_dirty_cycle(np.arange(100)[None, :, None]))
        time = np.arange(100)*2*np.pi/20
        samples = np.column_stack((np.sin(time), np.cos(time)))[None]
        self.assertIsNone(find_dirty_cycle(samples, find_minimum_cycle(samples)))


if __name__ == '__main__':
    unittest.main()
