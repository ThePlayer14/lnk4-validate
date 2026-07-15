# lnk4-validate

A small, dependency-light validation suite and **blueprint** for games that ship
assets in an **LNK4** container (e.g. *Code_18* — the title from the Snailium LNK4 write-up). The other titles validated using the suite include the Xbox 360 version of *11eyes CrossOver* and *Steins;Gate*.

It answers two questions about a container:

1. **Structure** — does this `.dat` have the entry count and outlier layout we
   expect for game *X*?
2. **Decode correctness** — does `libmsxca` turn every compressed entry into a
   valid payload (TIMG texture / binary blob)?

The whole project is plain Python + the `libmsxca` native decoder; no Windows-only
tools (`xbdecompress.exe`) required. The only real requirement in a Python environment is Pillow (for the image converter).

## Layout

```
lnk4-validate/
  check_game_profile.py   # CLI: check / init / extract
  lnk4lib.py              # LNK4 TOC parse + libmsxca classify helpers
  libmsxca/               # bundled copy of the libmsxca decoder (source + built libs)
    src/  CMakeLists.txt  BUILDING.md  README.md  ...
    build/libmsxca.so     # prebuilt for Linux x64
    runtimes/win-x64/native/msxca.dll   # prebuilt for Windows x64
  timg_converter/         # bundled TIMG <-> PNG converter (convert_timg.py)
  game_profiles/          # one JSON per known game
    elevene.json
    sg.json
    code18.json
  README.md
```

## The LNK4 format (short version)

* 4-byte magic `LNK4`, then a little-endian `data_ptr` (offset where blobs start).
* Table of 8-byte entries `(offset_blocks, length_blocks)`, little-endian, until a
  `(0, 0)` terminator.
  * `abs_offset = data_ptr + offset_blocks * 2048`
  * `length     = length_blocks * 1024`
* Each entry blob is either:
  * an **LZXNATIVE** compressed blob (magic `0FF512EE`) → decode with `libmsxca`,
    usually a **TIMG** texture, or
  * **raw bytes** already (e.g. an uncompressed PNG).

## Profiles

A profile is intentionally tiny — it records the parts that *vary per game* and
assumes everything else is the standard "compressed TIMG texture" case:

```json
{
  "game_id": "code18",
  "display_name": "Code_18",
  "source": "Snailium LNK4 container article",
  "container": {
    "format": "LNK4",
    "file": "to-test/code18-testdata/code18-lnk4/system.dat",
    "entry_count": 25,
    "size_bytes": 17426432
  },
  "outliers": {
    "always_png": [19],
    "binary_file": [24]
  },
  "image_entries": 23
}
```

* `always_png` — uncompressed entries that are already PNG (not in the container's
  compressed stream).
* `binary_file` — compressed entries whose decoded payload is **not** a TIMG
  (e.g. a not-yet known purpose blob saved as `.dec` by `crosslnk4`).
* Everything else (`entry_count - len(always_png) - len(binary_file)`) is expected
  to be a compressed TIMG texture.

`file` / `size_bytes` are resolved relative to `LNK4_VALIDATE_ROOT` (defaults to
the parent of this folder — the repo root).

## Bundled decoder (`libmsxca`)

A copy of [`libmsxca`](../../libmsxca) (cross-platform Xbox Compression / LZXNATIVE
decompressor, wrapping libmspack's `lzxd`) is bundled under `libmsxca/` so this
project is self-contained — no Windows-only tools and no dependency on the rest
of the repo. A Linux x64 build is prebuilt at `libmsxca/build/libmsxca.so` and
is used automatically.

To rebuild (e.g. for macOS/Windows, or after editing the source):

```sh
# Linux / macOS
cmake -S libmsxca -B libmsxca/build
cmake --build libmsxca/build

# Windows (cross-compile from Linux with MinGW-w64)
cmake -S libmsxca -B libmsxca/build-win64 \
    -DCMAKE_SYSTEM_NAME=Windows -DCMAKE_C_COMPILER=x86_64-w64-mingw32-gcc
cmake --build libmsxca/build-win64
# -> libmsxca.dll ; drop it at libmsxca/runtimes/win-x64/native/msxca.dll
```

`lnk4lib` resolves the native lib automatically per platform: the bundled
`build/libmsxca.so` (Linux), `runtimes/win-x64/native/msxca.dll` (Windows), or
`LIBMSXCA_SO` to override.

The loader searches (`lnk4lib._candidate_libs`) in this order:

1. `LIBMSXCA_SO` env var (if set)
2. `libmsxca/build/` inside this project (preferred)

> Note: the bundled copy builds with default symbol visibility (no
> `-fvisibility=hidden`) so `msxca_decompress` / `msxca_free` are exported on
> ELF without extra annotations.

## Bundled TIMG converter (`timg_converter`)

A `convert_timg.py` converter is bundled under
`timg_converter/`. It converts the decompressed **TIMG** payloads to viewable
PNGs (and back), interpreting the 8-byte little-endian header
(`width, height, depth, flag`; depth 8 = grayscale, 32 = ARGB) and the raw
pixel data. `extract` uses it to emit `<n>.png` alongside each `<n>.timg`.

This is preferred over `crosslnk4/lib/timg.py`: it is a standalone, portable tool
(both produce byte-identical PNGs) and keeps the project free of the Windows-only
`crosslnk4` dependency.

## Usage

```sh
# Validate a container against its profile (uses profile's 'file' by default)
python check_game_profile.py check code18
python check_game_profile.py check elevene testdata/lnk4/elevene-system.dat

# Auto-generate a profile stub for a NEW game, then review/tweak it
python check_game_profile.py init path/to/newgame-system.dat newgame
#   -> writes game_profiles/newgame.json

# Dump every entry (raw .timg for textures, .png viewable, .bin for blobs)
python check_game_profile.py extract path/to/system.dat out_dir
```

`check` exits non-zero on any mismatch (entry count, outlier indices, image count,
or file size) — handy as a CI / regression gate.

## Adding a new game (blueprint)

1. Drop the `system.dat` somewhere under the repo.
2. `python check_game_profile.py init <dat> <game_id>` → writes a profile with the
   outliers auto-detected by `libmsxca`.
3. Open the generated `game_profiles/<game_id>.json` and fix `display_name`/`source`.
4. (Optional) Extract and check-by-look the `.png`s / `.bin`s to confirm the outlier
   classification is right.
5. `python check_game_profile.py check <game_id>` should now PASS — and will catch
   future drift in that game's container.

## Notes / caveats

* The `is_timg` check is a heuristic (header dimensions + depth 8/32 + size fit).
  If a game ships textures with other depths, extend `lnk4lib.is_timg`.
* Reference PNGs produced by `crosslnk4` use a converter that differs from the
  plain TIMG→PNG path, so PNG *bytes* are **not** valid known-correct references.   
  Validate decode
  correctness with raw `.stream` or `.bin` known-correct references from genuine `xbdecompress.exe` output when
  available (as done for `elevene`), or rely on `libmsxca`'s proven byte-identical
  output for the same LZXNATIVE format.
* `libmsxca` is the cross-platform decoder (Linux `.so` bundled);
  on Windows/macOS point an `LIBMSXCA_SO` environment variable at `msxca.dll` / `libmsxca.dylib`.
