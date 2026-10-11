#!/usr/bin/env python3
"""Extract a local, raw GameCube ISO without third-party dependencies.

Usage: python tools/melee_anim/extract_iso.py melee.iso
       python tools/melee_anim/extract_iso.py melee.iso --list

Outputs files/ and sys/ plus extraction-manifest.json under orig/GALE01.
Every file is checked against its ISO extent with SHA256, including on reruns.
An incompatible DOL is refused before writing. For investigation of another
revision, use BOTH --allow-unverified and --output orig/OTHER_REVISION; do not
use that output with GALE01 addresses. --overwrite replaces differing files.

This supports raw ISO/GCM only, not RVZ, GCZ, NKit, or encrypted Wii discs.
Header/FST/DOL layout reference: Dolphin's DiscIO/DiscUtils.cpp and
DiscIO/FileSystemGCWii.cpp (https://github.com/dolphin-emu/dolphin).
The ISO is opened read-only; only named output files are created/replaced.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import tempfile
from typing import BinaryIO


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "orig" / "GALE01"
DEFAULT_CONFIG = REPO_ROOT / "config" / "GALE01" / "config.yml"
CHUNK_SIZE = 1024 * 1024
MANIFEST_NAME = "extraction-manifest.json"


class ExtractionError(ValueError):
    """Invalid image or an unsafe/conflicting extraction destination."""


@dataclass(frozen=True)
class Extent:
    path: str
    offset: int
    size: int


def read_at(source: BinaryIO, offset: int, size: int, image_size: int) -> bytes:
    if offset < 0 or size < 0 or offset + size > image_size:
        raise ExtractionError(f"Extent outside ISO: {offset:#x} + {size:#x}")
    source.seek(offset)
    data = source.read(size)
    if len(data) != size:
        raise ExtractionError("ISO changed or was truncated while reading")
    return data


def safe_name(raw: bytes) -> str:
    try:
        name = raw.decode("shift_jis")
    except UnicodeDecodeError as error:
        raise ExtractionError("Invalid Shift-JIS filename") from error
    if (not name or name in {".", ".."} or name[-1] in {".", " "}
            or any(ord(char) < 32 or char in '<>:"/\\|?*' for char in name)):
        raise ExtractionError(f"Unsafe filename: {name!r}")
    # Windows reserves these names even when followed by an extension.
    stem = name.split(".")[0].rstrip(" ").upper()
    reserved = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    reserved.update(f"{prefix}{digit}" for prefix in ("COM", "LPT")
                    for digit in "123456789\u00b9\u00b2\u00b3")
    if stem in reserved:
        raise ExtractionError(f"Windows reserved filename: {name!r}")
    return name


def inspect_iso(source: BinaryIO) -> tuple[dict, list[Extent], list[str]]:
    """Validate all structural bounds and destinations before extracting."""
    source.seek(0, os.SEEK_END)
    image_size = source.tell()
    boot = read_at(source, 0, 0x440, image_size)
    if struct.unpack_from(">I", boot, 0x1C)[0] != 0xC2339F3D:
        raise ExtractionError("Not a raw GameCube ISO (GameCube magic missing)")
    if boot[0x200:0x204] == b"NKIT":
        raise ExtractionError("NKit images must first be converted to a raw ISO")
    try:
        game_id = boot[:6].decode("ascii")
    except UnicodeDecodeError as error:
        raise ExtractionError("Invalid disc game ID") from error
    if not re.fullmatch(r"[A-Za-z0-9]{6}", game_id):
        raise ExtractionError("Invalid disc game ID")
    dol_offset, fst_offset, fst_size, fst_max_size = struct.unpack_from(">4I", boot, 0x420)
    if not 12 <= fst_size <= 128 * 1024 * 1024 or fst_max_size < fst_size:
        raise ExtractionError("Invalid FST size")
    if dol_offset < 0x2460 or fst_offset < 0x2460:
        raise ExtractionError("DOL or FST overlaps fixed system headers")
    fst = read_at(source, fst_offset, fst_size, image_size)
    root_type, root_parent, count = struct.unpack_from(">3I", fst)
    if root_type != 0x01000000 or root_parent != 0 or not 1 <= count <= fst_size // 12:
        raise ExtractionError("Invalid FST root/count")
    names_start = count * 12
    extents = []
    directories = ["files", "sys"]
    # (entry index, exclusive end index, path); FST directories are preorder.
    stack = [(0, count, "files")]
    destinations = {"files", "sys"}
    for index in range(1, count):
        while stack and index >= stack[-1][1]:
            stack.pop()
        if not stack:
            raise ExtractionError("FST entry has no parent")
        name_word, offset, length = struct.unpack_from(">3I", fst, index * 12)
        kind = name_word >> 24
        if kind not in (0, 1):
            raise ExtractionError("Invalid FST entry type")
        name_offset = names_start + (name_word & 0xFFFFFF)
        name_end = fst.find(b"\0", name_offset) if name_offset < fst_size else -1
        if name_end < 0:
            raise ExtractionError("FST name is out of bounds or unterminated")
        name = safe_name(fst[name_offset:name_end])
        path = f"{stack[-1][2]}/{name}"
        key = path.casefold()
        if key in destinations:
            raise ExtractionError(f"Duplicate destination (case insensitive): {path}")
        destinations.add(key)
        if kind:
            if offset != stack[-1][0] or not index < length <= stack[-1][1]:
                raise ExtractionError(f"Invalid directory parent/end: {path}")
            directories.append(path)
            stack.append((index, length, path))
        else:
            if offset + length > image_size:
                raise ExtractionError(f"File extent outside ISO: {path}")
            extents.append(Extent(path, offset, length))

    app_header = read_at(source, 0x2440, 0x20, image_size)
    app_size, trailer_size = struct.unpack_from(">2I", app_header, 0x14)
    app_length = 0x20 + app_size + trailer_size
    if 0x2440 + app_length > image_size:
        raise ExtractionError("Apploader extent outside ISO")
    dol_header = read_at(source, dol_offset, 0x100, image_size)
    offsets = struct.unpack_from(">18I", dol_header, 0)
    sizes = struct.unpack_from(">18I", dol_header, 0x90)
    dol_size = 0x100
    for offset, size in zip(offsets, sizes):
        if size:
            if offset < 0x100 or dol_offset + offset + size > image_size:
                raise ExtractionError("Invalid DOL section extent")
            dol_size = max(dol_size, offset + size)
    if dol_size == 0x100:
        raise ExtractionError("DOL contains no sections")
    system_extents = [Extent("sys/boot.bin", 0, 0x440),
                      Extent("sys/bi2.bin", 0x440, 0x2000),
                      Extent("sys/apploader.img", 0x2440, app_length),
                      Extent("sys/main.dol", dol_offset, dol_size),
                      Extent("sys/fst.bin", fst_offset, fst_size)]
    # Check these individually too, without loading the whole DOL into memory.
    for extent in system_extents:
        if extent.offset + extent.size > image_size:
            raise ExtractionError(f"System extent outside ISO: {extent.path}")
    header = {"game_id": game_id, "disc_number": boot[6], "revision": boot[7],
              "title": boot[0x20:0x400].split(b"\0", 1)[0].decode("shift_jis", "replace"),
              "size": image_size, "dol_offset": dol_offset,
              "fst_offset": fst_offset, "fst_size": fst_size, "fst_entries": count}
    return header, system_extents + extents, directories


def hash_extent(source: BinaryIO, offset: int, size: int, algorithm="sha256") -> str:
    digest = hashlib.new(algorithm)
    source.seek(offset)
    remaining = size
    while remaining:
        chunk = source.read(min(CHUNK_SIZE, remaining))
        if not chunk:
            raise ExtractionError("ISO/output changed or was truncated while hashing")
        digest.update(chunk)
        remaining -= len(chunk)
    return digest.hexdigest()


def check_destination(path: Path, *, directory=False) -> None:
    """Reject symlinks/junctions/reparse points at every existing ancestor."""
    for component in [*reversed(path.parents), path]:
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        reparse = getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        if stat.S_ISLNK(info.st_mode) or reparse:
            raise ExtractionError(f"Output contains a symlink/reparse point: {component}")
        if component != path or directory:
            if not stat.S_ISDIR(info.st_mode):
                raise ExtractionError(f"Expected output directory: {component}")
        elif not stat.S_ISREG(info.st_mode):
            raise ExtractionError(f"Expected regular output file: {component}")


def atomic_write(path: Path, write_content) -> None:
    check_destination(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".extract-", delete=False) as target:
            temporary = Path(target.name)
            write_content(target)
        check_destination(path)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def expected_dol_hash(config: Path) -> str:
    match = re.search(r"^hash:\s*([0-9a-fA-F]{40})\s*$", config.read_text(), re.MULTILINE)
    if not match:
        raise ExtractionError(f"Missing original DOL SHA1 in {config}")
    return match.group(1).lower()


def extract_iso(iso: Path, output: Path, *, config: Path = DEFAULT_CONFIG,
                overwrite=False, allow_unverified=False, list_only=False) -> dict:
    iso = Path(os.path.abspath(iso))
    output = Path(os.path.abspath(output))
    with iso.open("rb") as source:
        source_stat = os.fstat(source.fileno())
        header, extents, directories = inspect_iso(source)
        dol = next(item for item in extents if item.path == "sys/main.dol")
        dol_sha1 = hash_extent(source, dol.offset, dol.size, "sha1")
        expected_sha1 = expected_dol_hash(config)
        compatible = header["game_id"] == "GALE01" and dol_sha1 == expected_sha1
        if not compatible and (not allow_unverified or output == DEFAULT_OUTPUT):
            raise ExtractionError(
                f"Incompatible revision: {header['game_id']} rev {header['revision']}, "
                f"DOL SHA1 {dol_sha1}; expected {expected_sha1}. "
                "For separate investigation use --allow-unverified AND --output orig/OTHER_REVISION.")
        if list_only:
            return {"iso": header, "dol_sha1": dol_sha1,
                    "files": [vars(item) for item in extents]}
        check_destination(output, directory=True)
        manifest_path = output / MANIFEST_NAME
        check_destination(manifest_path)
        for directory in directories:
            check_destination(output / directory, directory=True)
        files = []
        unchanged = 0
        # Preflight all conflicts before writes. Never trust an old manifest.
        for extent in extents:
            path = output.joinpath(*PurePosixPath(extent.path).parts)
            check_destination(path)
            if path == iso or (path.exists() and os.path.samefile(path, iso)):
                raise ExtractionError("Output would replace the input ISO")
            sha256 = hash_extent(source, extent.offset, extent.size)
            same = False
            if path.exists():
                with path.open("rb") as existing:
                    same = path.stat().st_size == extent.size and hash_extent(existing, 0, extent.size) == sha256
                if not same and not overwrite:
                    raise ExtractionError(f"Existing file differs: {path}; use --overwrite to replace it")
            files.append({**vars(extent), "sha256": sha256, "unchanged": same})
        if manifest_path == iso or (manifest_path.exists() and os.path.samefile(manifest_path, iso)):
            raise ExtractionError("Manifest would replace the input ISO")
        iso_sha256 = hash_extent(source, 0, header["size"])
        if manifest_path.exists() and not overwrite:
            try:
                previous = json.loads(manifest_path.read_text(encoding="utf-8"))
                managed_manifest = (isinstance(previous, dict)
                                    and previous.get("schema_version") == 1
                                    and isinstance(previous.get("iso"), dict)
                                    and previous["iso"].get("sha256") == iso_sha256
                                    and previous.get("files") == [
                                        {key: value for key, value in item.items() if key != "unchanged"}
                                        for item in files])
            except (ValueError, UnicodeError):
                managed_manifest = False
            if not managed_manifest:
                raise ExtractionError(f"Existing manifest differs: {manifest_path}; use --overwrite to replace it")
        for directory in directories:
            path = output / directory
            check_destination(path, directory=True)
            path.mkdir(parents=True, exist_ok=True)
        for item in files:
            path = output / item["path"]
            if item.pop("unchanged"):
                unchanged += 1
                continue
            def copy_content(target, item=item):
                source.seek(item["offset"])
                remaining = item["size"]
                while remaining:
                    chunk = source.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        raise ExtractionError("ISO truncated during extraction")
                    target.write(chunk)
                    remaining -= len(chunk)
            atomic_write(path, copy_content)
        # Re-read every output, not just newly written files, to certify inventory.
        for item in files:
            path = output / item["path"]
            check_destination(path)
            with path.open("rb") as result:
                if path.stat().st_size != item["size"] or hash_extent(result, 0, item["size"]) != item["sha256"]:
                    raise ExtractionError(f"Output hash/size mismatch: {path}")
        final_stat = os.fstat(source.fileno())
        if (source_stat.st_size, source_stat.st_mtime_ns) != (final_stat.st_size, final_stat.st_mtime_ns):
            raise ExtractionError("Input ISO changed during extraction")
        manifest = {"schema_version": 1,
                    "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
                    "iso": {"filename": iso.name, **header, "sha256": iso_sha256},
                    "main_dol": {"sha1": dol_sha1, "expected_sha1": expected_sha1,
                                 "matches_GALE01_config": compatible},
                    "file_count": len(files), "game_file_count": len(files) - 5,
                    "total_extracted_bytes": sum(item["size"] for item in files),
                    "written_count": len(files) - unchanged, "unchanged_count": unchanged,
                    "all_output_hashes_verified": True, "files": files}
        contents = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        atomic_write(manifest_path, lambda target: target.write(contents))
        return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("iso", nargs="?", type=Path, default=REPO_ROOT / "melee.iso")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true", help="replace differing existing output files")
    parser.add_argument("--allow-unverified", action="store_true", help="permit another DOL revision in a separate output directory")
    parser.add_argument("--list", action="store_true", dest="list_only", help="validate and list extents without writing files")
    args = parser.parse_args()
    try:
        result = extract_iso(args.iso, args.output, overwrite=args.overwrite,
                             allow_unverified=args.allow_unverified, list_only=args.list_only)
    except (ExtractionError, OSError) as error:
        parser.exit(1, f"Extraction failed: {error}\n")
    if args.list_only:
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['iso']['game_id']} disc revision {result['iso']['revision']}; "
              f"DOL SHA1 {result['main_dol']['sha1']}")
        print(f"Verified {result['file_count']} files ({result['game_file_count']} game + 5 system), "
              f"{result['total_extracted_bytes']:,} bytes; "
              f"written {result['written_count']}, unchanged {result['unchanged_count']}")
        print(f"Manifest: {args.output / MANIFEST_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
