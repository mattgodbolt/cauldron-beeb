#!/usr/bin/env python3
"""Extract the original's graphics to PNG sheets, so they can be looked at.

    .venv/bin/python tools/zxgfx.py [--snap build/cauldron.z80] [--out build/gfx] [--check]

Everything is read from the snapshot's memory at the addresses the game
uses (docs/research/data.md has the formats):

    fonts.png        the four character sets: the panel's (CHARS 55874),
                     the landscape's two (CHARS 63744 and 64512) and the
                     underground's (glyphs at 59074 + 8 * code)
    sprites.png      the sprite routine's (25431) graphics, frame by frame
    columns.png      the 255 landscape columns (table at 60430)
    landscape.png    the 61 outdoor screens from the column map (57310)
    blocks.png       the 74 underground blocks (table at 45980)
    rooms.png        the 64 underground rooms (table at 47790)

--check runs the original's own drawing routines headless on SkoolKit's
simulator (57228 for a landscape screen, 45710 for a room) and compares
their screen with this tool's rendering, cell by cell, pixels and
attributes. It is the proof that the formats here are the original's.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zx import PALETTE, Spectrum  # noqa: E402

# Character sets: (name, CHARS value; glyph of code c is at CHARS + 8 * c).
FONTS = [
    ("panel and menu (CHARS 55874)", 55874),
    ("landscape A, columns 1-215 (CHARS 63744)", 63744),
    ("landscape B, columns 216-255 (CHARS 64512)", 64512),
    ("underground (59074 + 8 * code)", 59074),
]

# Sprite graphics: (first frame, rows, bytes wide, frames, seen drawn).
# The object types table at 42282 (8 bytes a type: graphic, rows, width,
# then four parameters) names most of these sets.
# A frame is rows * width bytes, row by row, one bit a pixel, no mask; the
# frames of a set follow each other. "Seen drawn" sets were drawn by 25431
# during play; the others are graphics between them whose geometry is
# inferred from their neighbours and their look.
SPRITES = [
    (42450, 8, 3, 1, True),
    (42474, 8, 3, 1, False),
    (43590, 24, 3, 4, True),
    (43878, 24, 3, 20, False),   # frogs, ingredients, bones, skulls, ... (45174, 45246 are set at start)
    (50800, 24, 3, 4, True),
    (51090, 24, 3, 8, True),     # two bytes after the set above
    (52948, 16, 2, 4, True),
    (53076, 16, 2, 4, False),
    (53204, 16, 2, 4, True),
    (53340, 24, 2, 4, False),    # the last type in the table at 42282
    (53532, 24, 2, 4, True),
    (53730, 16, 3, 4, True),
    (53922, 16, 3, 4, False),
    (54120, 24, 3, 8, True),
    (54696, 24, 3, 4, True),
    (54984, 24, 3, 4, True),
    (55272, 24, 3, 4, False),    # pumpkins
    (60100, 24, 2, 5, True),
]

LAND_COLS = 60430      # 14 bytes a column id (1-255): 7 x (ink, char), rows 16-22
LAND_MAP = 57310       # column ids, screen k is LAND_MAP + 32k .. + 31
LAND_SCREENS = 61      # then 64 columns repeat the first 64, for the wrap
LAND_FONT_SWITCH = 216  # ids from here use CHARS 64512, below it 63744
LAND_ATTR = 0x40       # the outdoor ATTR-P (BRIGHT 1, PAPER 0) under each INK
BLOCKS = 45980         # 24 bytes a block type (1-74): 4 rows x 2 x (inks, char, char)
ROOMS = 47790          # 40 bytes a room (0-63): 5 rows x 8 block types
UNDER_FONT = 59074
ROOM_TOP = 3           # character row of the first row of blocks
WHITE, GREY = (255, 255, 255), (90, 90, 90)


def load(snap):
    return Spectrum(snap).mem


def glyph(mem, base, code):
    return [mem[base + 8 * code + i] for i in range(8)]


def put_cell(px, x0, y0, rows, ink, paper):
    for y, b in enumerate(rows):
        for bit in range(8):
            px[x0 + bit, y0 + y] = ink if b & (0x80 >> bit) else paper


def attr_colours(attr):
    bright = (attr & 0x40) >> 3
    return PALETTE[(attr & 7) | bright], PALETTE[((attr >> 3) & 7) | bright]


def label_sheet(tiles, cols, pad=2, scale=2, title=None):
    """Lay (label, image) tiles out in a grid with their labels above."""
    tw = max(t.size[0] for _, t in tiles) + pad
    th = max(t.size[1] for _, t in tiles) + pad + 10
    rows = (len(tiles) + cols - 1) // cols
    top = 14 if title else 0
    sheet = Image.new("RGB", (cols * tw, rows * th + top), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    if title:
        d.text((2, 1), title, fill=WHITE)
    for i, (lab, t) in enumerate(tiles):
        x, y = (i % cols) * tw, top + (i // cols) * th
        d.text((x, y), str(lab), fill=WHITE)
        sheet.paste(t, (x, y + 10))
    return sheet.resize((sheet.size[0] * scale, sheet.size[1] * scale), Image.NEAREST)


# --- fonts -------------------------------------------------------------------

def fonts_sheet(mem):
    parts = []
    for name, base in FONTS:
        im = Image.new("RGB", (16 * 9 + 120, 6 * 9), (40, 40, 40))
        px = im.load()
        for c in range(32, 128):
            i = c - 32
            put_cell(px, (i % 16) * 9, (i // 16) * 9, glyph(mem, base, c), WHITE, (0, 0, 0))
        parts.append((name, im))
    return label_sheet(parts, 1, scale=3, title="codes 32-127, 16 a row")


# --- sprites -----------------------------------------------------------------

def sprite_image(mem, addr, rows, width):
    im = Image.new("RGB", (width * 8, rows))
    px = im.load()
    for y in range(rows):
        for xb in range(width):
            put_cell(px, xb * 8, y, [mem[addr + y * width + xb]], WHITE, (0, 0, 0))
    return im


def sprites_sheet(mem):
    tiles = []
    for first, rows, width, n, seen in SPRITES:
        for f in range(n):
            a = first + f * rows * width
            tiles.append((f"{a}{'' if seen else '?'}", sprite_image(mem, a, rows, width)))
    return label_sheet(tiles, 8, pad=12, scale=3,
                       title="address (? = not seen drawn, geometry inferred)")


# --- landscape ---------------------------------------------------------------

def column_cells(mem, cid):
    """The 7 cells (rows 16-22) of landscape column cid: (glyph rows, attr)."""
    rec = LAND_COLS + 14 * (cid - 1)
    chars = 64512 if cid >= LAND_FONT_SWITCH else 63744
    return [(glyph(mem, chars, mem[rec + 2 * r + 1]), LAND_ATTR | (mem[rec + 2 * r] & 7))
            for r in range(7)]


def column_image(mem, cid):
    im = Image.new("RGB", (8, 56))
    px = im.load()
    for r, (rows, attr) in enumerate(column_cells(mem, cid)):
        put_cell(px, 0, r * 8, rows, *attr_colours(attr))
    return im


def columns_sheet(mem):
    return label_sheet([(c, column_image(mem, c)) for c in range(1, 256)], 32, pad=4, scale=2,
                       title="landscape column ids 1-255 (rows 16-22)")


def landscape_sheet(mem, per_row=8):
    w = 256
    sheet = Image.new("RGB", (per_row * (w + 4), ((LAND_SCREENS + per_row - 1) // per_row) * 70),
                      (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    for k in range(LAND_SCREENS):
        x0, y0 = (k % per_row) * (w + 4), (k // per_row) * 70
        d.text((x0, y0), f"screen {k} ({LAND_MAP + 32 * k})", fill=WHITE)
        for c in range(32):
            sheet.paste(column_image(mem, mem[LAND_MAP + 32 * k + c]), (x0 + 8 * c, y0 + 12))
    return sheet.resize((sheet.size[0] * 2, sheet.size[1] * 2), Image.NEAREST)


# --- underground -------------------------------------------------------------

def block_cells(mem, btype):
    """16 cells of a block, row by row: (char code, attr) or None for 32."""
    d = BLOCKS + 24 * btype
    out = []
    for row in range(4):
        for half in range(2):
            inks, c1, c2 = mem[d], mem[d + 1], mem[d + 2]
            d += 3
            # 45847: the first char takes the high nibble, the second bits 0-2.
            out.append(None if c1 == 32 else (c1, 0x40 | (inks >> 4)))
            out.append(None if c2 == 32 else (c2, 0x40 | (inks & 7)))
    return out


def draw_block(px, mem, btype, x0, y0, blank_attr=None):
    for i, cell in enumerate(block_cells(mem, btype)):
        x, y = x0 + (i % 4) * 8, y0 + (i // 4) * 8
        if cell is None:
            if blank_attr is not None:
                put_cell(px, x, y, [0] * 8, *attr_colours(blank_attr))
            continue
        put_cell(px, x, y, glyph(mem, UNDER_FONT, cell[0]), *attr_colours(cell[1]))


def blocks_sheet(mem):
    tiles = []
    for t in range(1, 75):
        im = Image.new("RGB", (32, 32))
        draw_block(im.load(), mem, t, 0, 0, blank_attr=0)
        tiles.append((t, im))
    return label_sheet(tiles, 10, pad=6, scale=3, title="underground block types 1-74")


def room_image(mem, room, attr=5):
    """Character rows 3-22 of the screen as 45710 leaves them."""
    im = Image.new("RGB", (256, 160))
    px = im.load()
    for i in range(32 * 20):
        put_cell(px, (i % 32) * 8, (i // 32) * 8, [0] * 8, *attr_colours(attr))
    for br in range(5):
        for bc in range(8):
            t = mem[ROOMS + 40 * room + 8 * br + bc]
            if t:
                draw_block(px, mem, t, bc * 32, br * 32)
    return im


def rooms_sheet(mem):
    return label_sheet([(f"room {r}", room_image(mem, r)) for r in range(64)], 8, pad=6, scale=1)


# --- the check against the original's own routines ----------------------------

def run_routine(spec, addr):
    from skoolkit.simutils import PC, T
    m, r = spec.mem, spec.sim.registers
    sp = r[12] - 2
    m[sp], m[sp + 1] = 0x00, 0x60          # return to 24576, the sentinel
    r[12], r[PC], r[26] = sp, addr, 0
    spec.sim.trace(addr, 0x6000, 0, r[T] + 60 * 69888, 0, None, None, None, None, None)
    return r[PC] == 0x6000


def screen_cells(mem, row0, nrows):
    out = []
    for cy in range(row0, row0 + nrows):
        for cx in range(32):
            rows = []
            for i in range(8):
                y = cy * 8 + i
                rows.append(mem[16384 + ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2) + cx])
            out.append((tuple(rows), mem[22528 + cy * 32 + cx]))
    return out


def check(snap):
    bad = 0
    # Landscape: 57228 prints the 32 columns whose ids start at (23296).
    for k in range(LAND_SCREENS):
        spec = Spectrum(snap)
        m = spec.mem
        m[23693], m[23694], m[23697] = LAND_ATTR | 5, 0, 0   # ATTR-P, MASK-P, P-FLAG as outdoors
        p = LAND_MAP + 32 * k
        m[23296], m[23297] = p & 255, p >> 8
        if not run_routine(spec, 57228):
            print("landscape screen", k, "did not return")
            bad += 1
            continue
        want = []
        for r in range(7):
            for c in range(32):
                rows, attr = column_cells(m, m[p + c])[r]
                want.append((tuple(rows), attr))
        diff = sum(a != b for a, b in zip(screen_cells(m, 16, 7), want))
        bad += diff > 0
        if diff:
            print(f"landscape screen {k}: {diff} cells differ")
    # Rooms: 45710 draws room (23296) with background attribute (23297).
    for room in range(64):
        spec = Spectrum(snap)
        m = spec.mem
        m[23296], m[23297] = room, 5
        if not run_routine(spec, 45710):
            print("room", room, "did not return")
            bad += 1
            continue
        got = screen_cells(m, ROOM_TOP + 1, 19)
        want = []
        cells = {}
        for br in range(5):
            for bc in range(8):
                t = m[ROOMS + 40 * room + 8 * br + bc]
                if t:
                    for i, cell in enumerate(block_cells(m, t)):
                        if cell:
                            cells[(ROOM_TOP + br * 4 + i // 4, bc * 4 + i % 4)] = cell
        for cy in range(ROOM_TOP + 1, ROOM_TOP + 20):
            for cx in range(32):
                cell = cells.get((cy, cx))
                want.append((tuple(glyph(m, UNDER_FONT, cell[0])), cell[1]) if cell else ((0,) * 8, 5))
        diff = sum(a != b for a, b in zip(got, want))
        bad += diff > 0
        if diff:
            print(f"room {room}: {diff} cells differ")
    print("check:", "all match" if not bad else f"{bad} screens differ",
          f"({LAND_SCREENS} landscape screens, 64 rooms)")
    return bad == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snap", default="build/cauldron.z80")
    ap.add_argument("--out", default="build/gfx")
    ap.add_argument("--check", action="store_true", help="compare with the original's own routines")
    args = ap.parse_args()
    mem = load(args.snap)
    os.makedirs(args.out, exist_ok=True)
    for name, fn in [("fonts", fonts_sheet), ("sprites", sprites_sheet), ("columns", columns_sheet),
                     ("landscape", landscape_sheet), ("blocks", blocks_sheet), ("rooms", rooms_sheet)]:
        path = os.path.join(args.out, name + ".png")
        fn(mem).save(path)
        print("wrote", path)
    if args.check:
        return 0 if check(args.snap) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
