#!/usr/bin/env python3
"""Convert a Spectrum screen (.scr, or 6912 bytes at 16384 of a snapshot)
to MODE 1's bytes in the port's 256 x 192 layout (src/defs.6502), with a
palette for every line (decision 13).

    python3 tools/mkscreen.py original/Cauldron.scr build/data/title.bin [--png out.png]

MODE 1 has black and three inks; the title has six, but no line shows
more than four and few more than three. So each line has its own three
(BRIGHT ignored: the BBC has none), changed down the screen by the
interrupt's palette splits (src/irq.6502, decision 4's mechanism): one
logical colour a split, landing in the blank between two lines. The
splits are chosen to show the most lit pixels in their own colour, then
to be fewest, each where the logical colour it changes is unused on the
lines either side if it can be. A pixel whose colour its line hasn't got
shows the nearest the line has (lit pixels stay lit).

It also writes <out>.6502, the palette at VSync and the splits, which
src/main.6502 includes.
"""
import argparse
import collections
import os

# Spectrum colour (GRB order: 0 black, 1 blue, 2 red, 3 magenta, 4 green,
# 5 cyan, 6 yellow, 7 white) -> BBC physical colour (RGB order: 1 red,
# 2 green, 4 blue).
ZX_TO_BBC = [0, 4, 1, 5, 2, 6, 3, 7]
BBC_RGB = [((c & 1) * 255, (c >> 1 & 1) * 255, (c >> 2 & 1) * 255) for c in range(8)]
ZX_NAMES = ["black", "blue", "red", "magenta", "green", "cyan", "yellow", "white"]

# The interrupt's first split lands before row 1 whatever the screen
# (SPLIT_FIRST, src/irq.6502); the rest at any line after it.
FIRST_SPLIT_LINE = 8
# Splits closer than this many lines apart would race the interrupt.
MIN_GAP = 2


def zx_pixels(scr):
    """The 256 x 192 screen as Spectrum colours 0-7, row by row."""
    out = []
    for y in range(192):
        row = ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2)
        line = []
        for cx in range(32):
            attr = scr[6144 + (y // 8) * 32 + cx]
            ink, paper = attr & 7, (attr >> 3) & 7
            b = scr[row + cx]
            line += [ink if b & (0x80 >> bit) else paper for bit in range(8)]
        out.append(line)
    return out


def mode1_bytes(logical):
    """256 x 192 logical colours (0-3) -> 12K of MODE 1 screen memory."""
    mem = bytearray(32 * 24 * 16)
    for y in range(192):
        for x in range(0, 256, 4):
            v = 0
            for p in range(4):
                c = logical[y][x + p]
                v |= ((c >> 1) & 1) << (7 - p) | (c & 1) << (3 - p)
            cell = (y // 8) * 512 + (x // 8) * 16
            mem[cell + (8 if x & 4 else 0) + (y & 7)] = v
    return mem


def plan(px):
    """The palette for each line: logical 1-3's Spectrum colours (0 for
    none), changing one logical colour at a time, only where a split may
    land. Returns (palettes, splits), splits as (line, logical, colour)."""
    counts = [collections.Counter(c for c in line if c) for line in px]
    colours = sorted({c for cnt in counts for c in cnt})
    choices = [0] + colours
    states = [s for s in ((a, b, c) for a in choices for b in choices for c in choices)
              if len({x for x in s if x}) == len([x for x in s if x])]

    def lost(y, s):
        return sum(n for c, n in counts[y].items() if c not in s)

    def fragile(y, old, new):
        # 1 for each line beside the split that shows the colour it changes.
        return (counts[y - 1][old] > 0) + (counts[y][new] > 0)

    # Cost: lit pixels in the wrong colour, then splits, then splits that
    # need the horizontal blank (fragile). Lines before the first split
    # show the VSync palette.
    LOST, SPLIT = 1 << 20, 1 << 10
    best = {s: (lost(0, s) * LOST, None) for s in states}
    trail = [best]
    for y in range(1, 192):
        nxt = {}
        for s in states:
            here = lost(y, s) * LOST
            cands = [(best[s][0], s)]
            if y >= FIRST_SPLIT_LINE:
                for i in range(3):
                    for c in choices:
                        if c == s[i]:
                            continue
                        p = s[:i] + (c,) + s[i + 1:]
                        if p in best:
                            cands.append((best[p][0] + SPLIT + fragile(y, c, s[i]), p))
            cost, prev = min(cands)
            nxt[s] = (cost + here, prev)
        best = nxt
        trail.append(best)
    s = min(best, key=lambda k: best[k][0])
    pal = [None] * 192
    for y in range(191, -1, -1):
        pal[y] = s
        s = trail[y][s][1]
    splits = []
    for y in range(1, 192):
        for i in range(3):
            if pal[y][i] != pal[y - 1][i]:
                splits.append([y, i + 1, pal[y][i]])
    centre(splits, pal, counts)
    return pal, splits


def centre(splits, pal, counts):
    """Move each split to the middle of the lines it could land on without
    changing a pixel's colour, so it is as far as it can be from what it
    changes, keeping them MIN_GAP apart in order."""
    def shows(y, i):
        return counts[y][pal[y][i - 1]] > 0
    spans = []
    for y, i, c in splits:
        # The logical colour's last line showing the old colour, its first
        # the new: the split can land before any line after the one, up to
        # the other.
        lo = y - 1
        while lo >= 0 and pal[lo][i - 1] == pal[y - 1][i - 1] and not shows(lo, i):
            lo -= 1
        hi = y
        while hi < 192 and pal[hi][i - 1] == c and not shows(hi, i):
            hi += 1
        lo = max(lo + 1, FIRST_SPLIT_LINE)
        spans.append((lo, hi))
    order = sorted(range(len(splits)), key=lambda k: sum(spans[k]))
    pos = [(spans[k][0] + spans[k][1] + 1) // 2 for k in order]
    for n in range(1, len(order)):
        pos[n] = max(pos[n], pos[n - 1] + MIN_GAP)
    for n in range(len(order) - 1, -1, -1):
        pos[n] = min(pos[n], spans[order[n]][1])
        if n:
            pos[n - 1] = min(pos[n - 1], pos[n] - MIN_GAP)
    for n, k in enumerate(order):
        assert spans[k][0] <= pos[n] <= spans[k][1], (splits, spans, pos)
        splits[k][0] = pos[n]
    splits.sort()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scr")
    ap.add_argument("out")
    ap.add_argument("--png")
    args = ap.parse_args()
    scr = open(args.scr, "rb").read()[:6912]
    px = zx_pixels(scr)
    pal, splits = plan(px)
    # The palette each line shows, after centring the splits.
    vsync = list(pal[0])
    if not splits or splits[0][0] != FIRST_SPLIT_LINE:
        # (split 0 always lands: here it changes nothing)
        splits.insert(0, [FIRST_SPLIT_LINE, 1, vsync[0]])
    shown = []
    cur = list(vsync)
    k = 0
    for y in range(192):
        while k < len(splits) and splits[k][0] == y:
            cur[splits[k][1] - 1] = splits[k][2]
            k += 1
        shown.append(tuple(cur))

    def logical(y, c):
        if c == 0:
            return 0
        if c in shown[y]:
            return shown[y].index(c) + 1
        rgb = BBC_RGB[ZX_TO_BBC[c]]
        inks = [i for i in range(3) if shown[y][i]]
        return 1 + min(inks, key=lambda i: (sum((a - b) ** 2 for a, b in zip(rgb, BBC_RGB[ZX_TO_BBC[shown[y][i]]])),
                                            shown[y][i]))
    log = [[logical(y, c) for c in line] for y, line in enumerate(px)]
    lit = sum(1 for line in px for c in line if c)
    own = sum(1 for y, line in enumerate(px) for x, c in enumerate(line)
              if c and shown[y][log[y][x] - 1] == c)
    print(f"{args.out}: {len(splits)} splits; {own} of {lit} lit pixels in their own colour")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    open(args.out, "wb").write(mode1_bytes(log))
    base, _ = os.path.splitext(args.out)
    with open(base + ".6502", "w") as f:
        name = os.path.basename(args.scr)
        f.write(f"\\ Made by tools/mkscreen.py from {name}: its palette at VSync and its\n"
                f"\\ splits (decision 13). Never edited by hand.\n"
                f"TITLE_SPLITS = {len(splits)}\n"
                f"\\ Logical colours 0-3 from VSync.\n"
                f".title_phys\n"
                f"    EQUB {', '.join(str(ZX_TO_BBC[c]) for c in [0] + vsync)}\n"
                f"\\ Each split's logical colour and the physical colour it shows from\n"
                f"\\ its line.\n")
        f.write(".title_logical\n")
        for y, i, c in splits:
            f.write(f"    EQUB {i}    ; line {y}: {ZX_NAMES[c]}\n")
        f.write(".title_colour\n")
        for y, i, c in splits:
            f.write(f"    EQUB {ZX_TO_BBC[c]}\n")
        f.write("\\ T1's periods, as irq.6502's split_latch: split 0 to 1 first.\n.title_latch\n")
        for k in range(len(splits) - 1):
            f.write(f"    EQUW t1_period({splits[k + 1][0] - splits[k][0]})\n")
        f.write("    EQUW &FFFF, &FFFF               ; (none after the last)\n")
    if args.png:
        from PIL import Image
        im = Image.new("RGB", (256, 192))
        im.putdata([BBC_RGB[ZX_TO_BBC[shown[y][c - 1]]] if c else (0, 0, 0)
                    for y, line in enumerate(log) for c in line])
        im.resize((512, 384), Image.NEAREST).save(args.png)


if __name__ == "__main__":
    main()
