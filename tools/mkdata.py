#!/usr/bin/env python3
"""Make the port's data from the original, into build/data/ (never
committed: original/README.md).

    .venv/bin/python tools/mkdata.py [--snap build/cauldron.z80] [--out build/data]

The original's tables as they are (docs/research/data.md), 1 bit a pixel
where they're graphics; the drawing expands them to MODE 1 as it goes:

    landfont.bin   the landscape's two fonts, 64000-65535: glyph c of font
                   A at 8c - 256, of font B at 8c + 512
    landcols.bin   the column table, 60430: 14 bytes an id from 1, seven
                   (ink, char) pairs for rows 16-22
    landmap.bin    the landscape map, 57310: 61 screens of 32 ids, then
                   the 64 that repeat the first for the wrap
    blocks.bin     the underground blocks, 45980: 24 bytes a type from 0
    rooms.bin      the rooms, 47790: 40 bytes each, 5 rows of 8 types
    underfont.bin  the underground font, 59330 (glyph c at 8c - 256)

and the colour (decision 3), from tools/colourstudy.py's counts:

    landpal.bin    per landscape screen 8 bytes: the logical colour (0-3)
                   of each Spectrum ink 0-7; then per screen 4 bytes, the
                   BBC physical colours of logical 0-3
    roompal.bin    the same for each room
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colourstudy import best3, ink_counts, land_cells, room_cells  # noqa: E402
from zxgfx import LAND_COLS, LAND_MAP, LAND_SCREENS, ROOMS, BLOCKS, load  # noqa: E402

UNDER_GLYPHS = 59330
LAND_FONTS = 64000
# Spectrum colour (0 black, 1 blue, 2 red, 3 magenta, 4 green, 5 cyan,
# 6 yellow, 7 white) -> BBC physical colour (1 red, 2 green, 4 blue).
ZX_TO_BBC = [0, 4, 1, 5, 2, 6, 3, 7]


def rgb(zx):
    b = ZX_TO_BBC[zx]
    return (b & 1, b >> 1 & 1, b >> 2 & 1)


def colour_map(counts):
    """Logical colours for Spectrum inks 0-7, and BBC colours for logical
    0-3: the three inks with the most lit pixels get logical 1-3 (in ink
    order, so the map is stable), and any other ink the nearest of them
    by RGB, the commonest of those on a tie."""
    inks, _ = best3(counts)
    inks = sorted(inks)
    while len(inks) < 3:                # a band of fewer inks: pad with white
        inks.append(next(i for i in (7, 6, 5, 4, 3, 2, 1) if i not in inks))
    cmap = []
    for ink in range(8):
        if ink == 0:
            cmap.append(0)
        elif ink in inks:
            cmap.append(1 + inks.index(ink))
        else:
            near = min(inks, key=lambda i: (sum((a - b) ** 2 for a, b in zip(rgb(i), rgb(ink))),
                                            -counts.get(i, 0)))
            cmap.append(1 + inks.index(near))
    return cmap, [0] + [ZX_TO_BBC[i] for i in inks]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snap", default="build/cauldron.z80")
    ap.add_argument("--out", default="build/data")
    args = ap.parse_args()
    m = load(args.snap)
    os.makedirs(args.out, exist_ok=True)

    def write(name, data):
        with open(os.path.join(args.out, name), "wb") as f:
            f.write(bytes(data))

    write("landfont.bin", m[LAND_FONTS:65536])
    write("landcols.bin", m[LAND_COLS:LAND_COLS + 14 * 255])
    write("landmap.bin", m[LAND_MAP:LAND_MAP + 32 * LAND_SCREENS + 64])
    write("blocks.bin", m[BLOCKS:BLOCKS + 24 * 75])
    write("rooms.bin", m[ROOMS:ROOMS + 40 * 64])
    write("underfont.bin", m[UNDER_GLYPHS:UNDER_GLYPHS + 8 * 96])
    for name, units in (("landpal.bin", [land_cells(m, k) for k in range(LAND_SCREENS)]),
                        ("roompal.bin", [room_cells(m, r) for r in range(64)])):
        maps = [colour_map(ink_counts(cells)) for cells in units]
        write(name, [b for cmap, _ in maps for b in cmap] + [b for _, phys in maps for b in phys])


if __name__ == "__main__":
    main()
