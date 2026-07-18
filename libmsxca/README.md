# libmsxca

Cross-platform decompressor for Xbox Compression `LZXNATIVE` (magic `0FF512EE`) Xbox 360
`XMemCompress` / `Xbcompress` files.

## What it does

Decompresses Xbox 360 compressed data blobs that use the Xbox Compression "LZXNATIVE"
codec — the format produced by Microsoft's `xcompress.dll` and `xbcompress.exe`
tools. These blobs are commonly found inside LNK4 game containers (e.g. from
"11eyes CrossOver" and other Xbox 360 titles).
The library itself is basically a wrapper on top of `libmspack`.

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

## The origin of the project

Every pure-managed LZX decompression port tested (XMemCompressionDotNet, MonoGame
`LzxDecoder`, cabextract-derived decoders) fails on the Xbox Compression chunk framing or
has a separate decode bug. libmspack's `lzxd`, used with chunk-deframing and a
fresh decode context per block (`reset_interval = 0`,
`output_length = UncompressedBlockSize`), decodes blobs **byte-identically** to
the native codec.

The library name is a shorthand for "**X**box (360) **C**ompression **A**lgorithm", also coincidentally similar to the Xpress compression format reference doc, but that one wasn't useful for the project. 

## Tested with

|Building platform | Result |
|------|--------|
| Linux (gcc, clang) | Builds and passes |
| macOS (clang) | Builds and passes |
| Windows (MSVC) | Builds and passes |
| Windows (mingw64 cross-compile) | Builds and passes |

### Tested games
| Game resource | Result |
|------|--------|
| `elevene-system.dat` (LNK4, 11eyes CrossOver) | 38/38 compressed blobs decoded, SHA-256 verified against source files |
| `sg-system.dat` (LNK4, SteinsGate Xbox 360) | 61/61 entries, SHA-256 verified against source files |

* Note that there could be differences with untested games.

## License

- **libmsxca wrapper** (`msxca.c`, `msxca.h`): MIT — do what you want
- **libmspack** (`lzxd.c`, `lzx.h`, `mspack.h`, `system.h`, `system.c`,
  `macros.h`, `readbits.h`, `readhuff.h`): LGPL 2.1 — see
  [COPYING.LIB](https://github.com/kyzer/mspack/blob/master/COPYING.LIB)
  (libmspack by Stuart Caie)

# References 
* [LZX Delta documentation](https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-patch/cc78752a-b4af-4eee-88cb-01f4d8a4c2bf), also referred as "[MS-PATCH]"
* [Microsoft LZX Data format](https://learn.microsoft.com/en-us/previous-versions/bb417343(v=msdn.10)?redirectedfrom=MSDN#microsoft-lzx-data-compression-format), the Cabinets reference
