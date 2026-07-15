"""Shared LNK4 + libmsxca helpers for the lnk4-validate blueprint project.

A LNK4 container holds a TOC of 8-byte (offset_blocks, length_blocks) entries
packed at 2048/1024-byte units from a data pointer, followed by concatenated
entry blobs. Most entries are Xbox Compression `LZXNATIVE` (magic 0FF512EE)
blobs that decode to TIMG textures; a couple of outliers per game are not.
"""

import os
import struct
import ctypes

MAGIC_LNK4 = b"LNK4"
MAGIC_CMP = bytes.fromhex("0FF512EE")
MAGIC_PNG = b"\x89PNG"

_BLOCK = 2048
_LEN = 1024


def project_root():
    """Directory that contains this project (the repo root for this layout)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def repo_root():
    r = os.environ.get("LNK4_VALIDATE_ROOT")
    return os.path.abspath(r) if r else project_root()


def _candidate_libs():
    here = os.path.dirname(os.path.abspath(__file__))
    root = repo_root()
    cands = []
    if os.environ.get("LIBMSXCA_SO"):
        cands.append(os.environ["LIBMSXCA_SO"])
    # Local copy bundled with this project (preferred)
    cands.append(os.path.join(here, "libmsxca", "build", "libmsxca.so"))
    cands.append(os.path.join(here, "libmsxca", "runtimes", "win-x64", "native", "msxca.dll"))
    cands.append(os.path.join(here, "libmsxca", "build", "Release", "msxca.dll"))
    cands.append(os.path.join(here, "libmsxca", "build", "libmsxca.dylib"))
    # XcaExtractor bundled native libs (Linux / Windows / macOS)
    cands.append(os.path.join(root, "XcaExtractor/src/XcaExtractor.Core/runtimes/linux-x64/native/libmsxca.so"))
    cands.append(os.path.join(root, "XcaExtractor/src/XcaExtractor.Core/runtimes/win-x64/native/msxca.dll"))
    cands.append(os.path.join(root, "XcaExtractor/src/XcaExtractor.Core/runtimes/osx-x64/native/libmsxca.dylib"))
    # libmsxca CMake build output (repo root)
    cands.append(os.path.join(root, "libmsxca/build/libmsxca.so"))
    cands.append(os.path.join(root, "libmsxca/build/Release/msxca.dll"))
    return cands


_LIB = None


def libmsxca():
    """Load libmsxca (cross-platform Xbox Compression LZXNATIVE decoder)."""
    global _LIB
    if _LIB is not None:
        return _LIB
    for path in _candidate_libs():
        if os.path.exists(path):
            _LIB = ctypes.CDLL(path)
            return _LIB
    raise FileNotFoundError(
        "libmsxca native library not found. Set LIBMSXCA_SO or build libmsxca. Tried:\n  "
        + "\n  ".join(_candidate_libs())
    )


def decompress(blob):
    """Decompress one LZXNATIVE blob (magic 0FF512EE). Returns bytes or None."""
    lib = libmsxca()
    lib.msxca_decompress.restype = ctypes.c_int
    lib.msxca_decompress.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_size_t),
    ]
    c = ctypes.create_string_buffer(blob, len(blob))
    out = ctypes.c_void_p()
    out_len = ctypes.c_size_t()
    rc = lib.msxca_decompress(
        ctypes.cast(c, ctypes.c_void_p), ctypes.c_size_t(len(blob)),
        ctypes.byref(out), ctypes.byref(out_len),
    )
    if rc != 0:
        return None
    data = ctypes.string_at(out, out_len.value)
    lib.msxca_free(out)
    return data


def is_timg(buf):
    """Heuristic: does this decompressed payload look like a TIMG texture?"""
    if len(buf) < 6:
        return False
    w, h, depth = struct.unpack_from("<HHH", buf, 0)
    if depth not in (8, 32):
        return False
    if w == 0 or h == 0 or w > 16384 or h > 16384:
        return False
    return 6 + w * h * depth // 8 <= len(buf)


def parse_toc(data):
    """Return list of (abs_offset, length) for every LNK4 entry."""
    if data[:4] != MAGIC_LNK4:
        raise ValueError("not an LNK4 container")
    data_ptr = struct.unpack_from("<I", data, 4)[0]
    entries = []
    off = 8
    while off + 8 <= len(data):
        offset_blocks, length_blocks = struct.unpack_from("<II", data, off)
        off += 8
        if offset_blocks == 0 and length_blocks == 0:
            break
        entries.append((data_ptr + offset_blocks * _BLOCK, length_blocks * _LEN))
    return entries


def classify(data, entries):
    """Classify each entry index.

    Returns (always_png, binary_file, images) sorted index lists.
      always_png  - uncompressed entries that are already PNG
      binary_file - compressed entries whose payload is NOT a TIMG
      images      - everything else (compressed TIMG textures)
    """
    always_png, binary_file, images = [], [], []
    for i, (foff, flen) in enumerate(entries):
        blob = data[foff:foff + flen]
        if blob[:4] != MAGIC_CMP:
            if blob[:4] == MAGIC_PNG:
                always_png.append(i)
            else:
                binary_file.append(i)
            continue
        dec = decompress(blob)
        if dec is None or not is_timg(dec):
            binary_file.append(i)
        else:
            images.append(i)
    return sorted(always_png), sorted(binary_file), sorted(images)
