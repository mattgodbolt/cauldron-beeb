#!/usr/bin/env python3
"""Compare the BBC viewer's landscape screens and rooms with the
original's, byte for byte.

    .venv/bin/python tools/drawcmp.py [--snap build/cauldron.z80] [--png DIR]

tools/drawcheck.mjs dumps what the BBC drew (build/bbcdraw). This draws
the same from the original's data through tools/zxgfx.py's readers (which
its --check proves against the original's own drawing) and the colour
maps of decision 3 (tools/mkdata.py's, the same the disc has), into MODE 1
bytes, and compares the screen and the palette. --png writes each
mismatch side by side. Exits non-zero on any difference.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colourstudy import ink_counts, land_cells, room_cells  # noqa: E402
from mkdata import colour_map  # noqa: E402
from mkscreen import BBC_RGB  # noqa: E402
from zxgfx import LAND_SCREENS, load  # noqa: E402

LAND_ROW, ROOM_ROW = 16, 3


def expected(cells, row0, cmap):
    mem = bytearray(0x3000)
    for (r, c), (g, ink) in cells.items():
        mask = [0x00, 0x0F, 0xF0, 0xFF][cmap[ink]]
        base = (row0 + r) * 512 + c * 16
        for y, b in enumerate(g):
            mem[base + y] = (b >> 4) * 0x11 & mask
            mem[base + 8 + y] = (b & 15) * 0x11 & mask
    return mem


def image(mem, phys):
    from PIL import Image
    im = Image.new("RGB", (256, 192))
    px = im.load()
    for y in range(192):
        for x in range(256):
            b = mem[(y // 8) * 512 + (x // 8) * 16 + (8 if x & 4 else 0) + (y & 7)]
            p = x & 3
            px[x, y] = BBC_RGB[phys[((b >> (7 - p)) & 1) * 2 + ((b >> (3 - p)) & 1)]]
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snap", default="build/cauldron.z80")
    ap.add_argument("--png")
    args = ap.parse_args()
    m = load(args.snap)
    bad = 0
    jobs = [("land", k, land_cells(m, k), LAND_ROW) for k in range(LAND_SCREENS)]
    jobs += [("room", r, room_cells(m, r), ROOM_ROW) for r in range(64)]
    for name, n, cells, row0 in jobs:
        cmap, phys = colour_map(ink_counts(cells))
        want = expected(cells, row0, cmap)
        got = open(f"build/bbcdraw/{name}_{n:02d}.bin", "rb").read()
        scr, pal = got[:0x3000], list(got[0x3000:])
        diff = sum(a != b for a, b in zip(scr, want))
        if diff or pal != phys:
            bad += 1
            print(f"{name} {n}: {diff} bytes differ" + ("" if pal == phys else f", palette {pal} not {phys}"))
            if args.png:
                from PIL import Image
                os.makedirs(args.png, exist_ok=True)
                pair = Image.new("RGB", (520, 192))
                pair.paste(image(want, phys), (0, 0))
                pair.paste(image(scr, pal), (264, 0))
                pair.resize((1040, 384), Image.NEAREST).save(f"{args.png}/{name}_{n:02d}.png")
    print("drawcmp:", "all match" if not bad else f"{bad} differ", f"({LAND_SCREENS} landscape screens, 64 rooms)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
