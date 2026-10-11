"""Synthetic disc tests; no copyrighted game data is included."""

import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import unittest
import uuid

from tools.melee_anim.extract_iso import (
    DEFAULT_OUTPUT, ExtractionError, extract_iso, inspect_iso, safe_name,
)


def synthetic_disc(names=("models", "Mario.dat", "empty.dat", "root.dat")):
    image = bytearray(0x4000)
    image[:6] = b"GALE01"
    image[7] = 2
    image[0x20:0x2A] = b"Test disc\0"
    struct.pack_into(">I", image, 0x1C, 0xC2339F3D)
    strings = bytearray()
    name_offsets = []
    for name in names:
        name_offsets.append(len(strings))
        strings.extend(name.encode("shift_jis") + b"\0")
    entries = [(0x01000000, 0, 5),
               (0x01000000 | name_offsets[0], 0, 4),
               (name_offsets[1], 0x3000, 7),
               (name_offsets[2], 0x3007, 0),
               (name_offsets[3], 0x3100, 9)]
    fst = b"".join(struct.pack(">3I", *entry) for entry in entries) + strings
    struct.pack_into(">4I", image, 0x420, 0x2500, 0x2700, len(fst), len(fst))
    # One DOL code section; its extent, not the next disc structure, sets size.
    struct.pack_into(">I", image, 0x2500, 0x100)
    struct.pack_into(">I", image, 0x2590, 0x10)
    image[0x2600:0x2610] = b"synthetic code!!"
    struct.pack_into(">2I", image, 0x2454, 0x10, 0)
    image[0x2700:0x2700 + len(fst)] = fst
    image[0x3000:0x3007] = b"model!!"
    image[0x3100:0x3109] = b"root data"
    return bytes(image)


class InspectTests(unittest.TestCase):
    def test_nested_files_system_extents_and_empty_file(self):
        header, extents, directories = inspect_iso(io.BytesIO(synthetic_disc()))
        self.assertEqual(header["revision"], 2)
        self.assertEqual(header["fst_entries"], 5)
        self.assertEqual(directories, ["files", "sys", "files/models"])
        paths = {item.path: item for item in extents}
        self.assertEqual(paths["files/models/Mario.dat"].size, 7)
        self.assertEqual(paths["files/models/empty.dat"].size, 0)
        self.assertEqual(paths["sys/main.dol"].size, 0x110)
        self.assertEqual(paths["sys/apploader.img"].size, 0x30)

    def test_bad_magic_and_nkit(self):
        for offset, value in [(0x1C, b"BAD!"), (0x200, b"NKIT")]:
            with self.subTest(offset=offset):
                image = bytearray(synthetic_disc())
                image[offset:offset + 4] = value
                with self.assertRaises(ExtractionError):
                    inspect_iso(io.BytesIO(image))

    def test_truncated_system_data(self):
        with self.assertRaises(ExtractionError):
            inspect_iso(io.BytesIO(synthetic_disc()[:0x440]))

    def test_traversal_windows_names_and_invalid_encodings(self):
        for name in [b"", b"..", b"../escape", b"\\escape", b"C:escape",
                     b"NUL.dat", b"com1.txt", b"LPT9", b"file.", b"file ",
                     b"question?", b"quote\"", b"x\x00y", b"\x81"]:
            with self.subTest(name=name), self.assertRaises(ExtractionError):
                safe_name(name)
        self.assertEqual(safe_name(b"PlMrNr.dat"), "PlMrNr.dat")

    def test_duplicate_case_insensitive_destinations(self):
        with self.assertRaisesRegex(ExtractionError, "Duplicate destination"):
            inspect_iso(io.BytesIO(synthetic_disc(names=("models", "Mario.dat", "mario.DAT", "root.dat"))))

    def test_file_directory_collision(self):
        with self.assertRaisesRegex(ExtractionError, "Duplicate destination"):
            inspect_iso(io.BytesIO(synthetic_disc(names=("models", "Mario.dat", "empty.dat", "models"))))

    def test_bad_root_count_directory_parent_and_end(self):
        for offset, value in [(0x2708, 99999), (0x2710, 4), (0x2714, 6),
                              (0x2714, 1), (0x2700, 0)]:
            with self.subTest(offset=offset, value=value):
                image = bytearray(synthetic_disc())
                struct.pack_into(">I", image, offset, value)
                with self.assertRaises(ExtractionError):
                    inspect_iso(io.BytesIO(image))

    def test_unterminated_name_and_name_out_of_bounds(self):
        for mode in ("unterminated", "offset"):
            with self.subTest(mode=mode):
                image = bytearray(synthetic_disc())
                if mode == "offset":
                    struct.pack_into(">I", image, 0x2730, 0xFFFFFF)
                else:
                    fst_size = struct.unpack_from(">I", image, 0x428)[0]
                    image[0x2700 + fst_size - 1] = 0x41
                with self.assertRaises(ExtractionError):
                    inspect_iso(io.BytesIO(image))

    def test_out_of_bounds_file_fst_apploader_and_dol(self):
        for offset, value in [(0x271C, 0x4000), (0x424, 0x4000),
                              (0x2454, 0xFFFFFFFF), (0x2590, 0xFFFFFFFF),
                              (0x2500, 0x40)]:
            with self.subTest(offset=offset):
                image = bytearray(synthetic_disc())
                struct.pack_into(">I", image, offset, value)
                with self.assertRaises(ExtractionError):
                    inspect_iso(io.BytesIO(image))


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        # The managed Windows sandbox permits workspace writes; use an ignored
        # test directory rather than relying on the host's user Temp ACLs.
        temporary_base = Path(__file__).resolve().parents[3] / "build" / "melee_anim_tests"
        temporary_base.mkdir(parents=True, exist_ok=True)
        # Python 3.13 on Windows gives mkdtemp's mode=0700 a private ACL that
        # excludes the managed sandbox token. Ordinary mkdir inherits access.
        self.root = temporary_base / f"test-{uuid.uuid4().hex}"
        self.root.mkdir()
        self.assertTrue(self.root.resolve().is_relative_to(temporary_base.resolve()))
        self.addCleanup(shutil.rmtree, self.root)
        self.iso = self.root / "test.iso"
        self.iso.write_bytes(synthetic_disc())
        self.config = self.root / "config.yml"
        self.sha1 = hashlib.sha1(synthetic_disc()[0x2500:0x2610]).hexdigest()
        self.config.write_text(f"hash: {self.sha1}\n")
        self.output = self.root / "extracted"

    def extract(self, **kwargs):
        return extract_iso(self.iso, self.output, config=self.config, **kwargs)

    def test_extract_verify_manifest_and_idempotent_rerun(self):
        first = self.extract()
        self.assertEqual(first["file_count"], 8)
        self.assertEqual(first["game_file_count"], 3)
        self.assertEqual(first["written_count"], 8)
        self.assertTrue(first["all_output_hashes_verified"])
        self.assertEqual(first["iso"]["sha256"], hashlib.sha256(self.iso.read_bytes()).hexdigest())
        for item in first["files"]:
            data = (self.output / item["path"]).read_bytes()
            self.assertEqual(len(data), item["size"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])
        model = self.output / "files/models/Mario.dat"
        original_mtime = model.stat().st_mtime_ns
        second = self.extract()
        self.assertEqual(second["written_count"], 0)
        self.assertEqual(second["unchanged_count"], 8)
        self.assertEqual(model.stat().st_mtime_ns, original_mtime)
        manifest = json.loads((self.output / "extraction-manifest.json").read_text())
        self.assertEqual(manifest["files"], first["files"])
        self.assertEqual(self.iso.read_bytes(), synthetic_disc())

    def test_conflict_refusal_before_other_files_written_and_explicit_overwrite(self):
        conflict = self.output / "files/models/Mario.dat"
        conflict.parent.mkdir(parents=True)
        conflict.write_bytes(b"different")
        with self.assertRaisesRegex(ExtractionError, "Existing file differs"):
            self.extract()
        self.assertFalse((self.output / "sys/main.dol").exists())
        self.assertEqual(conflict.read_bytes(), b"different")
        self.extract(overwrite=True)
        self.assertEqual(conflict.read_bytes(), b"model!!")

    def test_missing_file_resume_and_corruption_is_not_trusted(self):
        self.extract()
        missing = self.output / "files/root.dat"
        missing.unlink()
        resumed = self.extract()
        self.assertEqual(resumed["written_count"], 1)
        self.assertEqual(missing.read_bytes(), b"root data")
        missing.write_bytes(b"bad bytes")
        with self.assertRaisesRegex(ExtractionError, "Existing file differs"):
            self.extract()

    def test_revision_refused_before_writes_and_explicit_separate_override(self):
        self.config.write_text("hash: " + "0" * 40 + "\n")
        with self.assertRaisesRegex(ExtractionError, "Incompatible revision"):
            self.extract()
        self.assertFalse(self.output.exists())
        manifest = self.extract(allow_unverified=True)
        self.assertFalse(manifest["main_dol"]["matches_GALE01_config"])
        with self.assertRaisesRegex(ExtractionError, "Incompatible revision"):
            extract_iso(self.iso, DEFAULT_OUTPUT, config=self.config, allow_unverified=True)

    def test_list_does_not_write(self):
        result = self.extract(list_only=True)
        self.assertEqual(result["dol_sha1"], self.sha1)
        self.assertEqual(len(result["files"]), 8)
        self.assertFalse(self.output.exists())

    def test_foreign_manifest_refused_before_writes(self):
        self.output.mkdir()
        manifest = self.output / "extraction-manifest.json"
        manifest.write_text("unrelated user file")
        with self.assertRaisesRegex(ExtractionError, "Existing manifest differs"):
            self.extract()
        self.assertFalse((self.output / "sys/main.dol").exists())
        self.assertEqual(manifest.read_text(), "unrelated user file")
        self.extract(overwrite=True)
        self.assertEqual(json.loads(manifest.read_text())["schema_version"], 1)

    def test_symlink_directory_and_file_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        self.output.mkdir()
        link = self.output / "files"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Symlink creation unavailable: {error}")
        with self.assertRaisesRegex(ExtractionError, "symlink/reparse"):
            self.extract(overwrite=True)
        self.assertEqual(list(outside.iterdir()), [])
        link.unlink()
        (self.output / "sys").mkdir()
        outside_file = outside / "main.dol"
        outside_file.write_bytes(b"preserve")
        (self.output / "sys/main.dol").symlink_to(outside_file)
        with self.assertRaisesRegex(ExtractionError, "symlink/reparse"):
            self.extract(overwrite=True)
        self.assertEqual(outside_file.read_bytes(), b"preserve")


if __name__ == "__main__":
    unittest.main()
