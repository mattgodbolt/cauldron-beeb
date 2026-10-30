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

    panelfont.bin  the panel and scenery font, 56130 (CHARS 55874: glyph
                   c at 8c - 256)
    scenery.bin    the scenery's PRINT strings, 55641-56096: the panel's
                   scrolls, the cottage's scrolls, the labels, the moon
                   and stars (src/scene.6502 has their offsets)

and the colour (decisions 3 and 4), from tools/colourstudy.py's counts:

    landpal.bin    per landscape screen 8 bytes: the logical colour (0-3)
                   of each Spectrum ink 0-7; then per screen 2 bytes, the
                   BBC physical colours of logical 1 and 3 (logical 2 is
                   always cyan, the sprites' colour: decision 4)
    roompal.bin    the same for each room
    sprites.bin    the sprite graphics' regions (SPRITE_REGIONS), one after
                   another: SPRITE takes the original's addresses, and
                   src/sprite.6502 finds each in its region
    logictab.bin   the tables the BASIC PEEKs and POKEs (LOGIC_REGIONS),
                   one after another: src/vmxlat.6502 finds each
    romfont.bin    the Spectrum ROM's font, for PRINT with CHARS 15360
    bandmaps.bin   the fixed bands' maps, 8 bytes each: the panel's rows
                   0-3, then the sky (decision 4's split layout)
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colourstudy import best3, ink_counts, land_cells, room_cells  # noqa: E402
from zxgfx import LAND_COLS, LAND_MAP, LAND_SCREENS, ROOMS, BLOCKS, load  # noqa: E402

UNDER_GLYPHS = 59330
# The tables the compiled BASIC reads and writes by address (measured in
# play, tools/zxaccess.py; docs/research/data.md), as (first, last + 1):
# PRINT's strings and the small tables; the object types and the room
# records; the rooms' entry places and exits; the data among the
# landscape's machine code (the start's room list at 56920). With them,
# what the USR routines the port transcribes read: the ending's, the game
# over's and the menu's texts, and the moon's attributes.
LOGIC_REGIONS = [(41575, 41732), (42169, 42274), (42274, 43589), (45320, 45704), (50388, 50762),
                 (52820, 52850), (56900, 57310)]
# The sprite graphics (docs/research/data.md), as (first, last + 1): the
# shots; the skeleton and its set; the witch on foot to the pumpkins
# (the code among them comes along); the last set.
SPRITE_REGIONS = [(42450, 42498), (43590, 45318), (50800, 55560), (60100, 60340)]
PANEL_GLYPHS = 56130
SCENERY, SCENERY_END = 55641, 56097
LAND_FONTS = 64000
# Spectrum colour (0 black, 1 blue, 2 red, 3 magenta, 4 green, 5 cyan,
# 6 yellow, 7 white) -> BBC physical colour (1 red, 2 green, 4 blue).
ZX_TO_BBC = [0, 4, 1, 5, 2, 6, 3, 7]


def rgb(zx):
    b = ZX_TO_BBC[zx]
    return (b & 1, b >> 1 & 1, b >> 2 & 1)


CYAN = 5                # the sprites' colour, always logical 2 below the panel


def nearest_map(logical, counts=None):
    """Logical colours for Spectrum inks 0-7, given {ink: logical} for the
    inks the band shows: any other ink takes the nearest of those by RGB
    (the commonest on a tie), black is logical 0."""
    counts = counts or {}
    cmap = []
    for ink in range(8):
        if ink == 0:
            cmap.append(0)
        elif ink in logical:
            cmap.append(logical[ink])
        else:
            near = min(logical, key=lambda i: (sum((a - b) ** 2 for a, b in zip(rgb(i), rgb(ink))),
                                               -counts.get(i, 0), i))
            cmap.append(logical[near])
    return cmap


def colour_map(counts):
    """The landscape's or a room's map (decision 4): cyan is logical 2,
    and the two other inks with the most lit pixels get logical 1 and 3
    (in ink order, so the map is stable). Returns the map and the BBC
    colours of logical 0-3."""
    inks, _ = best3({k: v for k, v in counts.items() if k != CYAN}, 2)
    inks = sorted(inks)
    while len(inks) < 2:                # a band of fewer inks: pad with white
        inks.append(next(i for i in (7, 6, 4, 3, 2, 1) if i not in inks))
    logical = {inks[0]: 1, CYAN: 2, inks[1]: 3}
    return nearest_map(logical, counts), [0, ZX_TO_BBC[inks[0]], ZX_TO_BBC[CYAN], ZX_TO_BBC[inks[1]]]


# The fixed bands (decision 4): the panel's rows show yellow as logical 1
# and green as 3, logical 2 magenta in rows 0 and 2 and cyan in 1 and 3
# (the inks each row has: magenta and yellow; green, cyan and yellow;
# magenta, green and yellow; cyan and yellow). The sky shows cyan as
# logical 2 and white as 3; logical 1 is the landscape's, set early.
PANEL_ROWS = [{6: 1, 3: 2, 4: 3}, {6: 1, 5: 2, 4: 3}, {6: 1, 3: 2, 4: 3}, {6: 1, 5: 2, 4: 3}]
SKY = {5: 2, 7: 3}


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
    write("panelfont.bin", m[PANEL_GLYPHS:PANEL_GLYPHS + 8 * 96])
    write("scenery.bin", m[SCENERY:SCENERY_END])
    write("logictab.bin", [b for a, e in LOGIC_REGIONS for b in m[a:e]])
    # ... and where each region starts in it, for src/vmxlat.6502.
    with open(os.path.join(args.out, "logicmap.6502"), "w") as f:
        f.write("\\ Made by tools/mkdata.py: LOGIC_REGIONS, and where each starts in logictab.\n")
        f.write("LT_FROM = {" + ", ".join(str(a) for a, _ in LOGIC_REGIONS) + "}\n")
        f.write("LT_TO = {" + ", ".join(str(e) for _, e in LOGIC_REGIONS) + "}\n")
        starts, at = [], 0
        for a, e in LOGIC_REGIONS:
            starts.append(at)
            at += e - a
        f.write("LT_AT = {" + ", ".join(map(str, starts)) + "}\n")
        f.write(f"LT_REGIONS = {len(LOGIC_REGIONS)}\n")
    write("sprites.bin", [b for a, e in SPRITE_REGIONS for b in m[a:e]])
    write("romfont.bin", m[15616:16384])             # the ROM's font, CHARS 15360: glyph c at 8c - 256
    write("bandmaps.bin", [b for band in PANEL_ROWS + [SKY] for b in nearest_map(band)])
    for name, units in (("landpal.bin", [land_cells(m, k) for k in range(LAND_SCREENS)]),
                        ("roompal.bin", [room_cells(m, r) for r in range(64)])):
        maps = [colour_map(ink_counts(cells)) for cells in units]
        write(name, [b for cmap, _ in maps for b in cmap] + [b for _, phys in maps for b in (phys[1], phys[3])])


if __name__ == "__main__":
    main()
