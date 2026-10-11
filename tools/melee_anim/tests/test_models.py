"""Synthetic model-layout cases; no original game data in tests."""

import struct
import unittest

from tools.melee_anim.hsd import Archive, FormatError
from tools.melee_anim.inspect_models import display_lists, envelopes, joints, resolved_filename


def archive(data, relocations=()):
    table = b"".join(struct.pack(">I", r) for r in relocations)
    return Archive(struct.pack(">5I12s", 32 + len(data) + len(table), len(data),
                               len(relocations), 0, 0, b"001B") + data + table)


class ModelTests(unittest.TestCase):
    def triangle(self):
        # Three vertices: direct matrix byte followed by big-endian u16 index.
        display = b"\x90\0\3" + b"\0\0\0\x03\0\1\0\0\0"
        data = display.ljust(32, b"\0") + struct.pack(">6h", -4, 8, 12, 16, -20, 24)
        attrs = [{"attribute": 0, "type": 1},
                 {"attribute": 9, "type": 3, "components": 1,
                  "component_type": 3, "frac": 2, "stride": 6, "array": 32}]
        return data, attrs

    def test_big_endian_indices_and_signed_fractional_positions(self):
        data, attrs = self.triangle()
        r = display_lists(archive(data), 0, 32, attrs)
        self.assertEqual(r["first_positions"], [[-1, 2, 3], [4, -5, 6], [-1, 2, 3]])
        self.assertEqual(r["matrix_indices"], [0, 3])
        self.assertEqual(r["max_indices"], {"POS": 1})
        self.assertEqual(r["triangle_slots_including_degenerates"], 1)

    def test_display_list_truncation(self):
        with self.assertRaises(FormatError):
            display_lists(archive(b"\x90\0"), 0, 2, [])

    def test_vertex_array_bounds(self):
        data, attrs = self.triangle()
        with self.assertRaises(FormatError):
            display_lists(archive(data[:-1]), 0, 32, attrs)

    def test_joint_cycle_and_relocated_zero(self):
        data = bytearray(64)
        # Relocated zero is a back-reference to root, not an empty child.
        with self.assertRaises(FormatError):
            joints(archive(bytes(data), (8,)), 0)

    def test_envelope_reference_must_resolve_in_skeleton(self):
        data = bytearray(40)
        struct.pack_into(">I", data, 0, 16)
        struct.pack_into(">If", data, 16, 32, 1.0)
        a = archive(bytes(data), (0, 16))
        self.assertEqual(envelopes(a, 0, {32: 7}), [[{"joint_index": 7, "weight": 1.0}]])
        with self.assertRaises(FormatError):
            envelopes(a, 0, {})

    def test_filename_locale_keeps_color_separate_from_language(self):
        self.assertEqual(resolved_filename("PlCaRe.", "us"), "PlCaRe.usd")
        self.assertEqual(resolved_filename("PlCaRe.", "jp"), "PlCaRe.dat")
        self.assertEqual(resolved_filename("PlMrNr.dat", "us"), "PlMrNr.dat")


if __name__ == "__main__":
    unittest.main()
