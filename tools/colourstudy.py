#!/usr/bin/env python3
"""How much of the original's colour each BBC screen scheme keeps.

    .venv/bin/python tools/colourstudy.py [--snap build/cauldron.z80]

Counts the lit pixels of each ink (BRIGHT folded: the BBC has none) in the
landscape (rows 16-22 of each of the 61 screens, from the column data) and
the rooms (the 64 rooms' blocks), from tools/zxgfx.py's readers, which its
--check proves against the original's own drawing. Paper is black
everywhere (docs/research/graphics.md), so a lit pixel shown in its own
ink is the measure. For each scheme it reports the share of lit pixels
shown in their own colour:

- one palette (three inks beside black) for a whole band, chosen per
  screen or room, which the push scroll and the flip rooms allow;
- two inks per screen, the third logical colour kept for the sprites;
- one palette per character row, chosen per screen (palette splits each
  row);
- MODE 2, which keeps every colour at half the horizontal resolution.

It also counts the pixels of the landscape whose 2-pixel pair is mixed
(one lit, one not), which MODE 2's halving has to lose or merge.
"""
import argparse
import collections
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zxgfx import (LAND_MAP, LAND_SCREENS, ROOMS, UNDER_FONT, block_cells,  # noqa: E402
                   column_cells, glyph, load)

NAMES = ["black", "blue", "red", "magenta", "green", "cyan", "yellow", "white"]


def popcount(b):
    return bin(b).count("1")


def land_cells(mem, k):
    """{(row 0-6, col): (glyph rows, ink)} for landscape screen k."""
    out = {}
    for c in range(32):
        for r, (rows, attr) in enumerate(column_cells(mem, mem[LAND_MAP + 32 * k + c])):
            out[(r, c)] = (rows, attr & 7)
    return out


def room_cells(mem, room):
    out = {}
    for br in range(5):
        for bc in range(8):
            t = mem[ROOMS + 40 * room + 8 * br + bc]
            if t:
                for i, cell in enumerate(block_cells(mem, t)):
                    if cell:
                        out[(br * 4 + i // 4, bc * 4 + i % 4)] = (glyph(mem, UNDER_FONT, cell[0]), cell[1] & 7)
    return out


def ink_counts(cells, rows=None):
    n = collections.Counter()
    for (r, _), (g, ink) in cells.items():
        if rows is None or r in rows:
            n[ink] += sum(popcount(b) for b in g)
    n.pop(0, None)
    return n


def best3(counts, n=3):
    """The n inks keeping the most lit pixels, and how many they keep."""
    inks = sorted(counts, key=counts.get, reverse=True)[:n]
    return inks, sum(counts[i] for i in inks)


def mixed_pairs(cells):
    """Lit pixels whose MODE 2 pair (pixels 2i, 2i+1) is half unlit."""
    n = 0
    for g, _ in cells.values():
        for b in g:
            for i in range(4):
                pair = (b >> (6 - 2 * i)) & 3
                n += pair in (1, 2)
    return n


def study(label, units, nrows):
    total = band = perrow = mixed = two = 0
    worst = []
    palettes = collections.Counter()
    for name, cells in units:
        counts = ink_counts(cells)
        t = sum(counts.values())
        if not t:
            continue
        inks, kept = best3(counts)
        palettes[tuple(sorted(inks))] += 1
        two += best3(counts, 2)[1]
        rowkept = sum(best3(ink_counts(cells, {r}))[1] for r in range(nrows))
        total += t
        band += kept
        perrow += rowkept
        mixed += mixed_pairs(cells)
        worst.append((kept / t, name, len(counts), ", ".join(f"{NAMES[i]} {counts[i]}" for i in sorted(counts))))
    print(f"\n## {label}\n")
    print(f"- lit pixels: {total}")
    print(f"- one 3-ink palette per screen: {100 * band / total:.2f}% in their own colour")
    print(f"- two inks per screen (one logical colour kept for sprites): {100 * two / total:.2f}%")
    print(f"- one 3-ink palette per character row: {100 * perrow / total:.2f}%")
    print(f"- MODE 2: 100% of colour; {100 * mixed / total:.1f}% of lit pixels are half of a mixed pair")
    print("- the palettes chosen, by how many screens:")
    for p, n in palettes.most_common():
        print(f"  - {' '.join(NAMES[i] for i in p)}: {n}")
    print("- the screens losing most with one palette:")
    for f, name, n, desc in sorted(worst)[:8]:
        print(f"  - {name}: {100 * f:.1f}% ({n} inks: {desc})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snap", default="build/cauldron.z80")
    args = ap.parse_args()
    mem = load(args.snap)
    study("The landscape (rows 16-22)", [(f"screen {k}", land_cells(mem, k)) for k in range(LAND_SCREENS)], 7)
    study("The rooms (rows 3-22)", [(f"room {r}", room_cells(mem, r)) for r in range(64)], 20)


if __name__ == "__main__":
    main()
