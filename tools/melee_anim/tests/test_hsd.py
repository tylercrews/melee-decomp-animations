import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hsd import Archive, Dol, FormatError


def archive(data=b"\0" * 8, relocations=(0,), publics=(("root", 0),)):
    names = bytearray()
    entries = bytearray()
    for name, offset in publics:
        entries += struct.pack(">II", offset, len(names))
        names += name.encode() + b"\0"
    tables = b"".join(struct.pack(">I", r) for r in relocations) + entries + names
    return struct.pack(">5I12s", 32 + len(data) + len(tables), len(data),
                       len(relocations), len(publics), 0, b"001B") + data + tables


class ArchiveTests(unittest.TestCase):
    def test_relocated_zero_is_not_null(self):
        a = Archive(archive())
        self.assertEqual(a.pointer(0), 0)
        self.assertIsNone(a.pointer(4))

    def test_first_duplicate_public_wins(self):
        a = Archive(archive(publics=(("root", 0), ("root", 4))))
        self.assertEqual(a.public("root"), 0)
        self.assertEqual(a.public_extent("root"), (0, 4))

    def test_out_of_range_and_truncation(self):
        for blob in (archive()[:-1], archive(relocations=(7,)), archive(publics=(("root", 9),))):
            with self.assertRaises(FormatError):
                Archive(blob)
        with self.assertRaises(FormatError):
            Archive(archive()).read(6, 4)

    def test_packed_alignment_and_boundary(self):
        first = archive()
        aligned = first + b"\xAA" * (-len(first) % 32)
        packed = aligned + first
        self.assertEqual([at for at, _ in Archive.parse_packed(packed)], [0, len(aligned)])
        with self.assertRaises(FormatError):
            Archive.parse_packed(packed[:-1])

    def test_unterminated_name(self):
        with self.assertRaises(FormatError):
            Archive(archive()[:-1] + b"x")


class DolTests(unittest.TestCase):
    def test_virtual_mapping_and_bss_rejection(self):
        blob = bytearray(264)
        struct.pack_into(">I", blob, 0, 256)
        struct.pack_into(">I", blob, 0x48, 0x80004000)
        struct.pack_into(">I", blob, 0x90, 8)
        blob[256:] = b"root\0\0\0\0"
        dol = Dol(bytes(blob))
        self.assertEqual(dol.cstring(0x80004000), "root")
        with self.assertRaises(FormatError):
            dol.read(0x80004007, 2)
        with self.assertRaises(FormatError):
            dol.read(0x80400000, 4)


if __name__ == "__main__":
    unittest.main()
