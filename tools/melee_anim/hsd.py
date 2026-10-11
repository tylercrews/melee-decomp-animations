"""Bounded readers for the original DAT and DOL layouts.

Layout references: tools/dat-cli/src/interop/{hsd,dol}.rs and
src/sysdolphin/baselib/archive.h. This is a focused inspection boundary,
not another type walker, runtime relocation system, or renderer.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path


class FormatError(ValueError):
    """Invalid or unsupported original data, with a useful location."""


class Archive:
    """One DAT archive; all object offsets are relative to its data region."""

    def __init__(self, blob: bytes | memoryview, label: str = "DAT"):
        self.label = label
        self.blob = memoryview(blob)
        if len(self.blob) < 32:
            raise FormatError(f"{label}: truncated header")
        (self.file_size, self.data_size, reloc_count,
         public_count, extern_count) = struct.unpack_from(">5I", self.blob)
        self.version = bytes(self.blob[20:32])
        if self.file_size != len(self.blob):
            raise FormatError(f"{label}: header size {self.file_size} != {len(self.blob)}")
        data_end = 32 + self.data_size
        names_at = data_end + reloc_count * 4 + (public_count + extern_count) * 8
        if names_at > len(self.blob):
            raise FormatError(f"{label}: data/tables exceed archive")
        self.data = self.blob[32:data_end]
        self.relocations = set()
        at = data_end
        for _ in range(reloc_count):
            offset = struct.unpack_from(">I", self.blob, at)[0]
            at += 4
            if offset + 4 > self.data_size:
                raise FormatError(f"{label}: relocation outside data at {offset:#x}")
            self.relocations.add(offset)
        self.publics = {}
        self.externs = {}
        self.public_entries = []
        self.extern_entries = []
        names = self.blob[names_at:]
        for count, entries, table in (
            (public_count, self.public_entries, self.publics),
            (extern_count, self.extern_entries, self.externs),
        ):
            for _ in range(count):
                offset, name_at = struct.unpack_from(">2I", self.blob, at)
                at += 8
                if offset > self.data_size and table is self.publics:
                    raise FormatError(f"{label}: public outside data at {offset:#x}")
                name = self._string(names, name_at, "symbol")
                entries.append((name, offset))
                table.setdefault(name, offset)  # game lookup: first match wins

    def read(self, offset: int, size: int) -> bytes:
        if offset < 0 or size < 0 or offset + size > self.data_size:
            raise FormatError(f"{self.label}: range {offset:#x}+{size:#x} exceeds data")
        return bytes(self.data[offset:offset + size])

    def u8(self, offset: int) -> int:
        return self.read(offset, 1)[0]

    def u16(self, offset: int) -> int:
        return struct.unpack(">H", self.read(offset, 2))[0]

    def u32(self, offset: int) -> int:
        return struct.unpack(">I", self.read(offset, 4))[0]

    def f32(self, offset: int) -> float:
        return struct.unpack(">f", self.read(offset, 4))[0]

    @staticmethod
    def _string(data: memoryview, offset: int, label: str) -> str:
        if not 0 <= offset < len(data):
            raise FormatError(f"{label}: string outside region at {offset:#x}")
        rest = bytes(data[offset:])
        end = rest.find(b"\0")
        if end < 0:
            raise FormatError(f"{label}: unterminated string at {offset:#x}")
        try:
            return rest[:end].decode("ascii")
        except UnicodeDecodeError as exc:
            raise FormatError(f"{label}: non-ASCII symbol at {offset:#x}") from exc

    def cstring(self, offset: int) -> str:
        return self._string(self.data, offset, self.label)

    string = cstring

    def pointer(self, offset: int) -> int | None:
        value = self.u32(offset)
        if offset in self.relocations:
            if value >= self.data_size:
                raise FormatError(f"{self.label}: pointer at {offset:#x} -> {value:#x} outside data")
            return value  # relocated zero points at data[0], rather than NULL
        if value in (0, 0xFFFFFFFF):
            return None
        raise FormatError(f"{self.label}: non-null unrelocated pointer at {offset:#x}")

    def public(self, name: str) -> int:
        try:
            return self.publics[name]
        except KeyError as exc:
            raise FormatError(f"{self.label}: no public {name}") from exc

    def public_extent(self, name: str) -> tuple[int, int]:
        start = self.public(name)
        end = min((at for _, at in self.public_entries if at > start),
                  default=self.data_size)
        return start, end - start

    @classmethod
    def parse_packed(cls, blob: bytes | memoryview, label: str = "packed DAT"):
        archives = []
        offset = 0
        while offset < len(blob):
            if offset + 32 > len(blob):
                raise FormatError(f"{label}: truncated packed header at {offset:#x}")
            size = struct.unpack_from(">I", blob, offset)[0]
            if size < 32 or offset + size > len(blob):
                raise FormatError(f"{label}: invalid packed size {size:#x} at {offset:#x}")
            archives.append((offset, cls(blob[offset:offset + size], f"{label}@{offset:#x}")))
            offset += (size + 31) & ~31
        return archives


class Dol:
    """Read initialized DOL data by virtual address (never BSS)."""

    def __init__(self, blob: bytes, label: str = "DOL"):
        self.label = label
        self.sections = []
        if len(blob) < 256:
            raise FormatError(f"{label}: truncated header")
        for i in range(18):
            offset = struct.unpack_from(">I", blob, i * 4)[0]
            address = struct.unpack_from(">I", blob, 0x48 + i * 4)[0]
            size = struct.unpack_from(">I", blob, 0x90 + i * 4)[0]
            if not size:
                continue
            if offset < 256 or offset + size > len(blob) or address + size > 2**32:
                raise FormatError(f"{label}: invalid section {i}")
            if any(address < a + len(d) and a < address + size for a, d in self.sections):
                raise FormatError(f"{label}: overlapping section {i}")
            self.sections.append((address, memoryview(blob)[offset:offset + size]))

    def read(self, address: int, size: int) -> bytes:
        for at, data in self.sections:
            offset = address - at
            if offset >= 0 and size >= 0 and offset + size <= len(data):
                return bytes(data[offset:offset + size])
        raise FormatError(f"{self.label}: no initialized range {address:#x}+{size:#x}")

    def u32(self, address: int) -> int:
        return struct.unpack(">I", self.read(address, 4))[0]

    def cstring(self, address: int) -> str:
        for at, data in self.sections:
            if at <= address < at + len(data):
                return Archive._string(data, address - at, self.label)
        raise FormatError(f"{self.label}: no initialized string at {address:#x}")

    string = cstring


def load_symbols(path: str | Path) -> dict[str, tuple[int, int]]:
    """Read named address/size entries from the checked-in DTK symbols file."""
    symbols = {}
    pattern = re.compile(r"^(\S+)\s*=\s*[^:;]+:(0x[0-9A-Fa-f]+);.*?\bsize:(0x[0-9A-Fa-f]+)")
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            symbols[match[1]] = (int(match[2], 16), int(match[3], 16))
    return symbols


def read_global(dol: Dol, symbols: dict, name: str) -> bytes:
    try:
        address, size = symbols[name]
    except KeyError as exc:
        raise FormatError(f"symbols: no sized global {name}") from exc
    return dol.read(address, size)
