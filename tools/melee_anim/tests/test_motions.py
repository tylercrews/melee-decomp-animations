import math
import struct
import unittest

from tools.melee_anim.hsd import Archive, FormatError
from tools.melee_anim.inspect_motions import motion_entries, read_exact_motion, script_summary
from tools.melee_anim.motions import Cursor, MotionError, Track, endpoint_report, read_figatree


def dat(data, relocations=(), publics=(("clip", 0),)):
    names = bytearray()
    entries = bytearray()
    for name, offset in publics:
        entries.extend(struct.pack(">II", offset, len(names)))
        names.extend(name.encode() + b"\0")
    tables = b"".join(struct.pack(">I", r) for r in relocations) + entries + names
    return struct.pack(">5I12s", 32 + len(data) + len(tables), len(data),
                       len(relocations), len(publics), 0, b"001B") + data + tables


def track(opcode, values, waits, slopes=None):
    raw = bytearray([((len(values) - 1) << 4) | opcode])
    for index, value in enumerate(values):
        raw.extend(struct.pack("<f", value))
        if slopes is not None:
            raw.extend(struct.pack("<f", slopes[index]))
        if index < len(waits):
            raw.extend(bytes([waits[index]]))
    return Track(0, 1, 0, 0, 0, bytes(raw))


class PackedTrackTests(unittest.TestCase):
    def test_mixed_endian_and_scaled_signed_values(self):
        cursor = Cursor(struct.pack("<f", 1.25) + struct.pack("<h", -384) + b"\xFF")
        self.assertEqual(cursor.scalar(0), 1.25)
        self.assertEqual(cursor.scalar(0x20 | 8), -1.5)
        self.assertEqual(cursor.scalar(0x60), -1)

    def test_packet_count_and_wait_variable_length(self):
        cursor = Cursor(bytes([0x82, 0x01, 0xAC, 0x02]))
        self.assertEqual(cursor.packet(), (2, 9))
        self.assertEqual(cursor.wait(), 300)

    def test_linear_first_terminal_and_unwrapped_endpoint(self):
        t = track(2, [2.0, 6.0], [4])
        self.assertEqual(t.evaluate(0), 2)
        self.assertEqual(t.evaluate(1), 3)
        self.assertEqual(t.evaluate(2), 4)
        self.assertEqual(t.evaluate(4), 6)
        self.assertEqual(t.packets(), {"linear": 2})
        self.assertAlmostEqual(endpoint_report([t], 4)["max_difference"], 2*math.pi - 4)

    def test_hermite_with_slopes_and_constant_steps(self):
        t = track(4, [0.0, 1.0], [4], [0.5, -0.25])
        self.assertEqual(t.evaluate(0), 0)
        self.assertAlmostEqual(t.evaluate(2), 0.875)
        self.assertEqual(t.evaluate(4), 1)
        step = track(1, [2.0, 6.0], [4])
        self.assertEqual(step.evaluate(3.99), 2)
        self.assertEqual(step.evaluate(4), 6)

    def test_zero_slope_and_slope_only_packet(self):
        t = track(3, [0.0, 1.0], [4])
        self.assertAlmostEqual(t.evaluate(1), 0.15625)
        # SPL0 key -> wait -> SLP tangent update -> LIN next key.
        # SLP persists the tangent before the next value consumes the wait.
        raw = (b"\x03" + struct.pack("<f", 0) + b"\x04\x05"
               + struct.pack("<f", .5) + b"\x02" + struct.pack("<f", 1))
        t = Track(0, 1, 0, 0, 0, raw)
        self.assertEqual(t.packets(), {"hermite_zero_slope": 1, "slope": 1, "linear": 1})
        self.assertAlmostEqual(t.evaluate(2), 0.25)

    def test_delayed_signed_start(self):
        original = track(2, [2, 6], [4])
        delayed = Track(0, 1, -2, 0, 0, original.data)
        self.assertIsNone(delayed.evaluate(1))
        self.assertEqual(delayed.evaluate(2), 2)
        self.assertEqual(delayed.evaluate(4), 4)

    def test_key_event_packet(self):
        t = track(6, [2, 6], [4])
        self.assertEqual(t.evaluate(0), 2)
        self.assertEqual(t.evaluate(3), 2)
        self.assertEqual(t.evaluate(4), 6)

    def test_terminal_key_does_not_hide_discontinuous_limit(self):
        raw = (b"\x01" + struct.pack("<f", 1) + b"\x02\x01"
               + struct.pack("<f", 0) + b"\x02\x03" + struct.pack("<f", 1))
        t = Track(0, 1, 0, 0, 0, raw)
        report = endpoint_report([t], 4)
        self.assertEqual(report["max_difference"], 0)
        self.assertEqual(report["max_limit_difference"], 1)

    def test_truncated_and_unknown_packets(self):
        for raw in (b"\x02\x00", b"\x07", b"\x12" + struct.pack("<f", 1) + b"\x80"):
            with self.assertRaises(MotionError):
                Track(0, 1, 0, 0, 0, raw).packets()


class MotionLayoutTests(unittest.TestCase):
    def test_visibility_and_texture_command_parameters(self):
        raw = struct.pack(">4I", 0x7C0FFFFF, 0xA2000803, 0, 0)
        summary = script_summary(Archive(dat(raw)), 0, bytes([1] * 49))
        visibility, texture = summary["commands"][:2]
        self.assertEqual((visibility["visibility_group"], visibility["visibility_value"]), (1, -1))
        self.assertEqual(texture["texture_animation"], {"both": True, "index": 0, "index2": 1, "frame": 3})

    def test_node_mapping_and_bounded_track_data(self):
        raw = track(2, [0, 1], [4]).data
        data = bytearray(36 + len(raw))
        struct.pack_into(">IIfII", data, 0, 1, 1 << 29, 4.0, 20, 24)
        data[20:24] = b"\0\x01\xFF\0"
        struct.pack_into(">HHBBBBI", data, 24, len(raw), 0, 1, 0, 0, 0, 36)
        data[36:] = raw
        metadata, tracks = read_figatree(Archive(dat(data, (12, 16, 32))), "clip")
        self.assertTrue(metadata["tree_loop"])
        self.assertEqual(metadata["node_count"], 2)
        self.assertEqual(tracks[0].joint_index, 1)
        struct.pack_into(">H", data, 26, 0xFFFF)
        _, delayed = read_figatree(Archive(dat(data, (12, 16, 32))), "clip")
        self.assertEqual(delayed[0].startframe, -1)
        struct.pack_into(">H", data, 24, len(raw) + 1)
        with self.assertRaises(FormatError):
            read_figatree(Archive(dat(data, (12, 16, 32))), "clip")

    def test_motion_table_loop_flag_independent_of_tree_flag(self):
        data = bytearray(56)
        struct.pack_into(">I", data, 12, 24)
        struct.pack_into(">6I", data, 24, 48, 0, 32, 0, 1 << 30, 0)
        data[48:53] = b"clip\0"
        motions = motion_entries(Archive(dat(data, (12, 24), (("ftData", 0),))), "ftData", 12, 1)
        self.assertTrue(motions[0]["motion_loop"])
        self.assertEqual(motions[0]["symbol"], "clip")

    def test_exact_motion_range_size_and_symbol(self):
        blob = dat(b"\0" * 20)
        entry = {"offset": 0, "size": len(blob), "symbol": "clip"}
        self.assertEqual(read_exact_motion(blob, entry, "packed").public("clip"), 0)
        with self.assertRaises((FormatError, MotionError)):
            read_exact_motion(blob, {**entry, "size": len(blob) - 1}, "packed")
        with self.assertRaises(FormatError):
            read_exact_motion(blob, {**entry, "symbol": "missing"}, "packed")


if __name__ == "__main__":
    unittest.main()
