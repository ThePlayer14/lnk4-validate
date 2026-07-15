# libmsxca

Cross-platform decompressor for Xbox Compression `LZXNATIVE` (magic `0FF512EE`) Xbox 360
`XMemCompress` / `Xbcompress` files.

## What it does

Decompresses Xbox 360 compressed data blobs that use the Xbox Compression "LZXNATIVE"
codec — the format produced by Microsoft's `xcompress.dll` and `xbcompress.exe`
tools. These blobs are commonly found inside LNK4 game containers (e.g. from
"11eyes CrossOver" and other Xbox 360 titles).

The library handles the full decoding pipeline:

1. Validates the 48-byte big-endian header (magic `0FF512EE`)
2. Parses window size, uncompressed size, and block-size fields
3. Iterates over compressed blocks, each preceded by a 4-byte BE size
4. Strips the 2-byte BE chunk-framing length prefixes from each block's data
5. Feeds the deframed data to libmspack's LZX (`lzxd`) decoder with a fresh
   decode context per block
6. Returns the fully decompressed output

## What it does NOT do

**Compression / recompression is not supported.** There is no open-source or
cross-platform `LZXNATIVE` *encoder*. Recompression requires Microsoft's
proprietary `xcompress.dll` (`XMemCompress`) on Windows.

## Why this exists

Every pure-managed LZX decompression port tested (XMemCompressionDotNet, MonoGame
`LzxDecoder`, cabextract-derived decoders) fails on the Xbox Compression chunk framing or
has a separate decode bug. libmspack's `lzxd`, used with chunk-deframing and a
fresh decode context per block (`reset_interval = 0`,
`output_length = UncompressedBlockSize`), decodes blobs **byte-identically** to
the native codec.

## Tested with

| What | Result |
|------|--------|
| `elevene-system.dat` (LNK4, 11eyes CrossOver) | 38/38 compressed blobs decoded, SHA-256 verified against source files |
| `sg-system.dat` (LNK4, SteinsGate Xbox 360) | 61/61 entries, SHA-256 verified against source files |
| 200+ LZXNATIVE blobs total | Byte-identical to `xbdecompress.exe` output |
| Linux (gcc, clang) | Builds and passes |
| macOS (clang) | Builds and passes |
| Windows (MSVC) | Builds and passes |
| Windows (mingw64 cross-compile) | Builds and passes |

## License

- **libmsxca wrapper** (`msxca.c`, `msxca.h`): MIT — do what you want
- **libmspack** (`lzxd.c`, `lzx.h`, `mspack.h`, `system.h`, `system.c`,
  `macros.h`, `readbits.h`, `readhuff.h`): LGPL 2.1 — see
  [COPYING.LIB](https://github.com/kyzer/mspack/blob/master/COPYING.LIB)
  (libmspack by Stuart Caie)
