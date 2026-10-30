#!/usr/bin/env python3
"""Compare the BBC viewer's scenes with the original's, byte for byte.

    .venv/bin/python tools/drawcmp.py [--snap build/cauldron.z80] [--png DIR]

tools/drawcheck.mjs dumps what the BBC drew (build/bbcdraw); tools/zxscene.py
has the original's own code draw the same scenes (build/zxscenes). This
turns each Spectrum screen into the MODE 1 bytes decision 4's colours
make of it (each row's band's map of the inks: tools/mkdata.py's, the
same the disc has) and compares the screen, the attributes, and the
lower band's colours. --png writes each mismatch side by side, the
original's on the left. Exits non-zero on any difference.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colourstudy import ink_counts, land_cells, room_cells  # noqa: E402
from mkdata import PANEL_ROWS, SKY, colour_map, nearest_map  # noqa: E402
from mkscreen import BBC_RGB  # noqa: E402
from zxgfx import LAND_SCREENS, load  # noqa: E402


def row_maps(outdoors, lower):
    panel = [nearest_map(r) for r in PANEL_ROWS]
    sky = nearest_map(SKY)
    return panel + [sky if outdoors and r < 16 else lower for r in range(4, 24)]


def mode1(scr, maps):
    """A Spectrum screen as MODE 1 bytes, each cell's lit pixels in its
    ink's logical colour on black paper."""
    mem = bytearray(0x3000)
    for cy in range(24):
        for cx in range(32):
            attr = scr[6144 + cy * 32 + cx]
            assert attr & 0x38 == 0, f"paper not black at row {cy}, column {cx}"
            mask = [0x00, 0x0F, 0xF0, 0xFF][maps[cy][attr & 7]]
            base = cy * 512 + cx * 16
            for i in range(8):
                y = cy * 8 + i
                b = scr[((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2) + cx]
                mem[base + i] = (b >> 4) * 0x11 & mask
                mem[base + 8 + i] = (b & 15) * 0x11 & mask
    return mem


def image(mem, maps_phys):
    """MODE 1 bytes drawn with each row's physical colours (logical 0-3)."""
    from PIL import Image
    im = Image.new("RGB", (256, 192))
    px = im.load()
    for y in range(192):
        phys = maps_phys[y // 8]
        for x in range(256):
            b = mem[(y // 8) * 512 + (x // 8) * 16 + (8 if x & 4 else 0) + (y & 7)]
            p = x & 3
            px[x, y] = BBC_RGB[phys[((b >> (7 - p)) & 1) * 2 + ((b >> (3 - p)) & 1)]]
    return im


# Each row's physical colours of logical 0-3 (decision 4), for pictures.
PANEL_PHYS = [[0, 3, 5, 2], [0, 3, 6, 2], [0, 3, 5, 2], [0, 3, 6, 2]]


def rows_phys(outdoors, phys):
    sky = [0, phys[1], 6, 7]
    return PANEL_PHYS + [sky if outdoors and r < 16 else phys for r in range(4, 24)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snap", default="build/cauldron.z80")
    ap.add_argument("--png")
    args = ap.parse_args()
    m = load(args.snap)
    bad = 0
    jobs = [("out", k, True, land_cells(m, k)) for k in range(LAND_SCREENS)]
    jobs += [("room", r, False, room_cells(m, r)) for r in range(64)]
    for name, n, outdoors, cells in jobs:
        lower, phys = colour_map(ink_counts(cells))
        maps = row_maps(outdoors, lower)
        scr = open(f"build/zxscenes/{name}_{n:02d}.scr", "rb").read()
        want = mode1(scr, maps)
        got = open(f"build/bbcdraw/{name}_{n:02d}.bin", "rb").read()
        gscr, gattrs, gpal = got[:0x3000], got[0x3000:0x3300], list(got[0x3300:])
        diff = sum(a != b for a, b in zip(gscr, want))
        adiff = sum(a != b for a, b in zip(gattrs, scr[6144:]))
        wpal = [phys[1], phys[3]]
        if diff or adiff or gpal != wpal:
            bad += 1
            print(f"{name} {n}: {diff} screen bytes and {adiff} attributes differ"
                  + ("" if gpal == wpal else f", colours {gpal} not {wpal}"))
            if args.png:
                from PIL import Image
                os.makedirs(args.png, exist_ok=True)
                rp = rows_phys(outdoors, phys)
                pair = Image.new("RGB", (520, 192))
                pair.paste(image(want, rp), (0, 0))
                pair.paste(image(gscr, rp), (264, 0))
                pair.resize((1040, 384), Image.NEAREST).save(f"{args.png}/{name}_{n:02d}.png")
    print("drawcmp:", "all match" if not bad else f"{bad} differ",
          f"({LAND_SCREENS} outdoor scenes, 64 rooms: screen, attributes, colours)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
