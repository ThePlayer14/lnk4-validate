#!/usr/bin/env python3
"""lnk4-validate - LNK4 container validation blueprint.

Commands:
  check   <game_id> [dat]      Validate a container against game_profiles/<id>.json
  init    <dat> <game_id>      Scan a container and write a profile stub
  extract <dat> <outdir>       Decompress every entry (for eyeballing / oracles)

A "profile" records the LNK4 entry count and the two per-game outliers:
  always_png  - an uncompressed entry that is already a PNG
  binary_file - a compressed entry whose payload is NOT a TIMG texture
Every other entry is expected to be a compressed TIMG texture.

Paths in profiles are resolved relative to LNK4_VALIDATE_ROOT (defaults to
the parent of this project; i.e. the repo root). libmsxca is located via
LIBMSXCA_SO or a few well-known locations.
"""

import os
import sys
import json
import shutil

import lnk4lib


def _resolve(path):
    if os.path.isabs(path):
        return path
    return os.path.join(lnk4lib.repo_root(), path)


def cmd_check(args):
    game_id = args[0]
    profile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_profiles", f"{game_id}.json")
    if not os.path.exists(profile_path):
        print(f"no profile for '{game_id}' ({profile_path})")
        return 2
    prof = json.load(open(profile_path))
    dat_path = _resolve(args[1]) if len(args) > 1 else _resolve(prof["container"]["file"])
    if not os.path.exists(dat_path):
        print(f"container not found: {dat_path}")
        return 2

    data = open(dat_path, "rb").read()
    entries = lnk4lib.parse_toc(data)
    always_png, binary_file, images = lnk4lib.classify(data, entries)

    errors = []
    if len(entries) != prof["container"]["entry_count"]:
        errors.append(f"entry_count {len(entries)} != profile {prof['container']['entry_count']}")
    if always_png != sorted(prof["outliers"]["always_png"]):
        errors.append(f"always_png {always_png} != profile {prof['outliers']['always_png']}")
    if binary_file != sorted(prof["outliers"]["binary_file"]):
        errors.append(f"binary_file {binary_file} != profile {prof['outliers']['binary_file']}")
    if len(images) != prof["image_entries"]:
        errors.append(f"image_entries {len(images)} != profile {prof['image_entries']}")
    if "size_bytes" in prof["container"] and len(data) != prof["container"]["size_bytes"]:
        errors.append(f"size {len(data)} != profile {prof['container']['size_bytes']}")

    print(f"game {game_id}: entries={len(entries)} always_png={always_png} "
          f"binary_file={binary_file} images={len(images)}")
    if errors:
        print("FAIL:")
        for e in errors:
            print("  -", e)
        return 1
    print("PASS")
    return 0


def cmd_init(args):
    dat_path = _resolve(args[0])
    game_id = args[1]
    data = open(dat_path, "rb").read()
    entries = lnk4lib.parse_toc(data)
    always_png, binary_file, images = lnk4lib.classify(data, entries)

    rel = os.path.relpath(os.path.abspath(dat_path), lnk4lib.repo_root())
    prof = {
        "game_id": game_id,
        "display_name": game_id,
        "source": "Snailium LNK4 container article",
        "container": {
            "format": "LNK4",
            "file": rel,
            "entry_count": len(entries),
            "size_bytes": len(data),
        },
        "outliers": {
            "always_png": always_png,
            "binary_file": binary_file,
        },
        "image_entries": len(images),
    }
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_profiles", f"{game_id}.json")
    json.dump(prof, open(out_path, "w"), indent=2)
    print(f"wrote {out_path}")
    print(f"  entries={len(entries)} always_png={always_png} binary_file={binary_file} images={len(images)}")
    print("  review display_name/source before committing.")
    return 0


def cmd_extract(args):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "timg_converter"))
    from convert_timg import bin_to_png
    dat_path = _resolve(args[0])
    out_dir = args[1]
    os.makedirs(out_dir, exist_ok=True)
    data = open(dat_path, "rb").read()
    entries = lnk4lib.parse_toc(data)
    for i, (foff, flen) in enumerate(entries):
        blob = data[foff:foff + flen]
        if blob[:4] == lnk4lib.MAGIC_CMP:
            dec = lnk4lib.decompress(blob)
            if dec is None:
                open(os.path.join(out_dir, f"{i:04d}.FAIL"), "wb").write(blob)
                continue
            if lnk4lib.is_timg(dec):
                timg_path = os.path.join(out_dir, f"{i:04d}.timg")
                open(timg_path, "wb").write(dec)
                try:
                    bin_to_png(timg_path, os.path.join(out_dir, f"{i:04d}.png"))
                except Exception as e:
                    print(f"[{i}] png: {e}")
            else:
                open(os.path.join(out_dir, f"{i:04d}.bin"), "wb").write(dec)
        else:
            ext = ".png" if blob[:4] == lnk4lib.MAGIC_PNG else ".bin"
            open(os.path.join(out_dir, f"{i:04d}{ext}"), "wb").write(blob)
    print(f"extracted {len(entries)} entries to {out_dir}")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd, args = sys.argv[1], sys.argv[2:]
    dispatch = {"check": cmd_check, "init": cmd_init, "extract": cmd_extract}
    if cmd not in dispatch:
        print(__doc__)
        return 2
    return dispatch[cmd](args)


if __name__ == "__main__":
    sys.exit(main())
