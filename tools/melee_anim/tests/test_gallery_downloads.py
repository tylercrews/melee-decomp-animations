import hashlib
import json
from pathlib import Path
import shutil
import unittest
import uuid
from zipfile import ZipFile

from tools.melee_anim.preview_batch import action_sections, completed_job
from tools.melee_anim.preview_gallery import collect_clips, write_bundle, write_still_bundle


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.build = Path("build/melee_anim_tests").resolve()
        self.root = self.build / f"downloads_{uuid.uuid4().hex}"
        self.root.mkdir(parents=True)

    def tearDown(self):
        target = self.root.resolve()
        if not target.is_relative_to(self.build) or not target.name.startswith("downloads_"):
            raise RuntimeError("Refusing unexpected test cleanup path")
        shutil.rmtree(target)

    def fixture(self, costume, action="taunt", section="source"):
        folder = self.root/"mario"/f"costume_{costume:02d}"/f"{action}_{section}"
        folder.mkdir(parents=True)
        model = self.root/f"model_{costume}.json"
        model.write_text(f"model {costume}")
        manifest = {"complete_interval": True, "action": action, "section": section,
                    "costume_id": costume, "sample_source_times": [0, 1],
                    "fps": 50, "camera_yaw": 0, "nominal_ticks_per_second": 60,
                    "source_period_frames": 2, "source_symbol": "synthetic_clip",
                    "authored_loop": False, "size": 256,
                    "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest()}
        (folder/"preview-manifest.json").write_text(json.dumps(manifest))
        for i in range(2):
            (folder/f"frame_{i:04d}.png").write_bytes(b"synthetic PNG placeholder")
        (folder/"preview.gif").write_bytes(b"GIF89a"+bytes([costume]))
        return folder, model

    def test_bundle_saves_distinct_colors_under_unique_names(self):
        self.fixture(0)
        self.fixture(3)
        clips = collect_clips(self.root)
        self.assertEqual({c["costume_id"] for c in clips}, {0, 3})
        bundle = self.root/"colors.zip"
        write_bundle(self.root, bundle, clips)
        with ZipFile(bundle) as archive:
            names = [n for n in archive.namelist() if n.endswith(".gif")]
            self.assertEqual(len(names), 2)
            self.assertEqual(len(set(names)), 2)
            self.assertTrue(any("red.gif" in n for n in names))
            self.assertTrue(any("blue.gif" in n for n in names))
            self.assertNotEqual(archive.read(names[0]), archive.read(names[1]))
            manifest = json.loads(archive.read("manifest.json"))
            for row in manifest["files"]:
                self.assertEqual(row["sha256"], hashlib.sha256(archive.read(row["file"])).hexdigest())

    def test_resume_refuses_missing_stale_frames_or_changed_model(self):
        folder, model = self.fixture(0)
        self.assertTrue(completed_job(folder, model, "taunt", "source", 256))
        (folder/"frame_9999.png").write_bytes(b"unexpected")
        self.assertFalse(completed_job(folder, model, "taunt", "source", 256))
        (folder/"frame_9999.png").unlink()
        (folder/"frame_0001.png").unlink()
        self.assertFalse(completed_job(folder, model, "taunt", "source", 256))
        with self.assertRaises(ValueError):
            collect_clips(self.root)
        (folder/"frame_0001.png").write_bytes(b"restored frame")
        model.write_text("changed model")
        self.assertFalse(completed_job(folder, model, "taunt", "source", 256))

    def test_all_includes_every_intro_and_wait_without_duplicates(self):
        jobs = action_sections("all", "all")
        self.assertEqual(len(jobs), 8)
        self.assertEqual(len(set(jobs)), 8)
        self.assertIn(("taunt", "source"), jobs)
        self.assertIn(("results-clap", "source"), jobs)
        for i in range(1, 4):
            self.assertIn((f"victory{i}", "source"), jobs)
            self.assertIn((f"victory{i}", "wait"), jobs)
        with self.assertRaises(ValueError):
            action_sections("taunt", "wait")

    def test_still_bundle_contains_the_selected_frame_of_each_costume(self):
        folders = [self.fixture(c)[0] for c in (0, 3)]
        for costume, folder in zip((0, 3), folders):
            (folder/'frame_0000.png').write_bytes(bytes([costume, 0]))
            (folder/'frame_0001.png').write_bytes(bytes([costume, 1]))
        clips = collect_clips(self.root)
        path = self.root/'frame-0002.zip'
        path.write_bytes(b'interrupted ZIP')
        write_still_bundle(self.root, path, clips, 1)
        with ZipFile(path) as archive:
            self.assertEqual(len(archive.namelist()), 2)
            for clip in clips:
                name = clip['download_name'].replace('.gif', '-frame-0002.png')
                self.assertEqual(archive.read(name), bytes([clip['costume_id'], 1]))
        # A re-rendered source must invalidate a previously complete bundle.
        (folders[0]/'frame_0001.png').write_bytes(b'changed pose')
        write_still_bundle(self.root, path, clips, 1)
        with ZipFile(path) as archive:
            name = clips[0]['download_name'].replace('.gif', '-frame-0002.png')
            self.assertEqual(archive.read(name), b'changed pose')


if __name__ == "__main__":
    unittest.main()
