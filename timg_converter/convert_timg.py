#!/usr/bin/env python3
"""TImg converter based on the crosslnk4 image converter.

TImg is a tiny container used by crosslnk4's image conversion code. Layout (little-endian):

    offset  size  field
    0x00    2     width
    0x02    2     height
    0x04    2     depth        (8 = grayscale, 32 = ARGB)
    0x06    2     flag         (1 if depth == 8 else 0)
    0x08    ...   raw pixel data

Pixel data:
    depth 32 -> 4 bytes/pixel in ARGB byte order (a, r, g, b)
    depth  8 -> 1 byte/pixel, 8-bit grayscale

Usage:
    convert_timg.py --to-png  <input.bin>            # -> png_output/<name>.png
    convert_timg.py --to-raw  <input.png>            # -> raw_output/<name>.bin

<input> may be a single file or a directory (batch conversion).
"""

import argparse
import os
import struct
import sys

from PIL import Image

TIMG_HEADER = struct.Struct("<HHHH")  # width, height, depth, flag
HEADER_SIZE = TIMG_HEADER.size        # 8 bytes


def check_header(data):
    """Return True if the first bytes look like a valid TImg header."""
    if len(data) < 6:
        return False
    _, _, depth = struct.unpack("<HHH", data[:6])
    return depth != 0


def bin_to_png(bin_path, png_path):
    with open(bin_path, "rb") as f:
        header = f.read(HEADER_SIZE)
        width, height, depth, _flag = TIMG_HEADER.unpack(header)
        raw_data = f.read()

    if depth == 32:
        img = Image.frombuffer("RGBA", (width, height), raw_data, "raw", "ARGB")
    elif depth == 8:
        img = Image.frombuffer("L", (width, height), raw_data, "raw")
    else:
        print(f"Warning: unexpected depth {depth} in {bin_path}; assuming ARGB32.")
        img = Image.frombuffer("RGBA", (width, height), raw_data, "raw", "ARGB")

    img.save(png_path)
    print(f"-> {png_path}  ({width}x{height}, depth={depth})")


def png_to_bin(png_path, bin_path, force_depth=None):
    img = Image.open(png_path)

    if force_depth == 8:
        depth = 8
    elif force_depth == 32:
        depth = 32
    else:
        depth = 8 if img.mode == "L" else 32

    width, height = img.size
    flag = 1 if depth == 8 else 0
    header = TIMG_HEADER.pack(width, height, depth, flag)

    if depth == 32:
        img = img.convert("RGBA")
        r, g, b, a = img.split()
        img_argb = Image.merge("RGBA", (a, r, g, b))
        raw_data = img_argb.tobytes()
    else:
        img = img.convert("L")
        raw_data = img.tobytes()

    with open(bin_path, "wb") as f:
        f.write(header)
        f.write(raw_data)
    print(f"-> {bin_path}  ({width}x{height}, depth={depth})")


def _iter_inputs(path, ext):
    if os.path.isdir(path):
        for name in sorted(os.listdir(path)):
            if name.lower().endswith(ext):
                yield os.path.join(path, name)
    else:
        yield path


def main():
    parser = argparse.ArgumentParser(description="Convert TImg (.bin) <-> PNG.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--to-png", metavar="INPUT",
                       help="Convert a TImg .bin file (or folder) to PNG.")
    group.add_argument("--to-raw", metavar="INPUT",
                       help="Convert a PNG file (or folder) to TImg .bin.")
    parser.add_argument("--out", help="Output directory (default: png_output / raw_output).")
    parser.add_argument("--depth", type=int, choices=[8, 32],
                        help="Force depth for --to-raw (8 or 32).")
    args = parser.parse_args()

    if args.to_png:
        out_dir = args.out or "png_output"
        ext_in, ext_out = ".bin", ".png"
        convert = bin_to_png
    else:
        out_dir = args.out or "raw_output"
        ext_in, ext_out = ".png", ".bin"
        convert = lambda src, dst: png_to_bin(src, dst, force_depth=args.depth)

    os.makedirs(out_dir, exist_ok=True)

    count = 0
    for src in _iter_inputs(args.to_png or args.to_raw, ext_in):
        base = os.path.splitext(os.path.basename(src))[0]
        dst = os.path.join(out_dir, base + ext_out)
        try:
            convert(src, dst)
            count += 1
        except Exception as e:
            print(f"Failed: {src}: {e}", file=sys.stderr)

    print(f"\nDone. {count} file(s) written to '{out_dir}'.")


if __name__ == "__main__":
    main()
