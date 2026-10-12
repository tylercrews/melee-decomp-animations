import unittest
import numpy as np
from io import BytesIO
from PIL import Image
from tools.melee_anim.sync_claps import fit_schedule, timeline_indices
from tools.melee_anim.gif_export import encode_frames
from tools.melee_anim.downloads import resize_gif


class SyncClapTests(unittest.TestCase):
    def test_schedule_respects_moving_speed_holds_and_exact_duration(self):
        for length in (12, 13, 15, 17, 20, 21, 25, 33, 34):
            schedule = fit_schedule(length)
            repeats, hold, rate = (schedule[k] for k in ('repeats', 'hold_frames_per_cycle', 'moving_rate'))
            self.assertLessEqual(abs(rate-1), .20+1e-9)
            self.assertLessEqual(hold, 3)
            self.assertAlmostEqual(repeats*(length/rate+hold), 42)
        with self.assertRaises(ValueError):
            fit_schedule(109)

    def test_source_sampling_is_continuous_and_contact_aligned_without_an_endpoint(self):
        schedule = fit_schedule(25)
        times = timeline_indices(7, 25, 5, 17, schedule)
        self.assertEqual(len(times), 42)
        self.assertAlmostEqual(times[0], 12)
        self.assertTrue(all(7 <= t < 32 for t in times))
        self.assertTrue(any(abs(t-round(t)) > 1e-6 for t in times))
        np.testing.assert_allclose(times[:21], times[21:])

    def test_buffer_repeats_a_single_open_pose_instead_of_stretching_the_whole_clip(self):
        schedule = fit_schedule(34)
        times = timeline_indices(0, 34, 0, 12, schedule)
        self.assertTrue(any(abs(times[i]-times[i+1]) < 1e-8 for i in range(41)))
        self.assertTrue(all(0 <= t < 34 for t in times))
        self.assertAlmostEqual(times[0], 0)

    def test_gif_encoder_and_resize_keep_every_held_timestep(self):
        palette = [0, 0, 0, 255, 0, 0, 0, 255, 0]+[0]*759
        frames = []
        for i in range(42):
            frame = Image.new('P', (16, 16), 1 if i < 20 else 2)
            frame.putpalette(palette)
            frames.append(frame)
        data = encode_frames(frames, [20]*42, 0)
        for output in [data, resize_gif(data, 128, preserve_frames=True)]:
            with Image.open(BytesIO(output)) as im:
                self.assertEqual(im.n_frames, 42)
                self.assertEqual(im.info['loop'], 0)
                for i in range(42):
                    im.seek(i)
                    self.assertEqual(im.info['duration'], 20)
                    self.assertEqual(im.convert('RGB').getpixel((0, 0)), (255, 0, 0) if i < 20 else (0, 255, 0))


if __name__ == '__main__':
    unittest.main()
