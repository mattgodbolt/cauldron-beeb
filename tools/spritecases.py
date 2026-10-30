#!/usr/bin/env python3
"""SPRITE on the BBC against SPRITE in the original (25431), on random
cases.

    .venv/bin/python tools/spritecases.py gen [--count N] [--seed S]
    node tools/spritecheck.mjs
    .venv/bin/python tools/spritecases.py cmp [--png DIR]

`gen` makes the cases (build/sprite/cases.json): a scene (an outdoor one
or a room, as tools/zxscene.py draws them), ATTR_P, ATTR_T and MASK_T,
three parameter blocks filled with graphics from the original's sprite
sets at random places (rows past column 31 among them: SPRITE doesn't
clip), modes and attributes, and a list of calls, a block drawn and later
drawn again (its erase) among others. It runs each on the original,
writing the screen before the calls (case_NNN_bg.scr) and after them
(case_NNN.scr). tools/spritecheck.mjs runs them on the BBC.

`cmp` checks the BBC's against them. The attributes must be the
original's. The pixels are modelled: SPRITE's XOR through the
Spectrum's screen addresses (model_calls), which must leave exactly the
original's lit pixels, coloured by decision 5's rule: a pixel the XOR
lights takes its cell's scenery colour if the scenery had it lit, the
sprite's colour if not; one it leaves lit keeps its colour. The BBC's
screen must be that, byte for byte. Exits non-zero on any difference.
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drawcmp import image, row_maps, rows_phys  # noqa: E402
from colourstudy import ink_counts, land_cells, room_cells  # noqa: E402
from mkdata import colour_map  # noqa: E402
from skoolkit.simutils import H, L  # noqa: E402
from zx import Spectrum  # noqa: E402
from zxgfx import LAND_ATTR, LAND_MAP, LAND_SCREENS, load, run_routine  # noqa: E402

OUT = "build/sprite"
BLOCKS = 24759
ATTR_P, MASK_P, ATTR_T, MASK_T, P_FLAG = 23693, 23694, 23695, 23696, 23697
SPRITE = 25431
# Graphic sets (docs/research/data.md): first frame, rows, width, frames.
SETS = [(42450, 8, 3, 2), (43590, 24, 3, 4), (43878, 24, 3, 20), (50800, 24, 3, 4), (51090, 24, 3, 8),
        (52300, 32, 4, 4), (53532, 24, 2, 4), (52948, 16, 2, 4), (53204, 16, 2, 4), (53532, 24, 2, 4), (53730, 16, 3, 4),
        (54120, 24, 3, 8), (54696, 24, 3, 4), (54984, 24, 3, 4), (55272, 24, 3, 4), (60100, 24, 2, 5)]
ATTRS = [67, 69, 71, 2, 4, 5, 7, 66, 68]
# The doors' graphics (src/sprite.6502's DOOR_FROM, DOOR_TO): their pixels
# take their cell's ink (decision 5).
DOORS = [(52300, 52300 + 4 * 128), (53532, 53532 + 4 * 48)]


def gen_case(rnd):
    outdoors = rnd.random() < 0.5
    scene = rnd.randrange(LAND_SCREENS if outdoors else 64)
    blocks = []
    for _ in range(3):
        first, rows, width, frames = rnd.choice(SETS)
        y = rnd.randrange(rows - 1, 176)
        x = rnd.choice([rnd.randrange(256), rnd.randrange(224, 256), rnd.randrange(0, 256, 8)])
        blocks.append([first + rows * width * rnd.randrange(frames), x, y, rows, width,
                       rnd.randrange(3), rnd.choice(ATTRS)])
    calls = [rnd.randrange(3) for _ in range(rnd.randrange(1, 7))]
    return {"outdoors": outdoors, "scene": scene, "attr_p": rnd.choice([71, 69, 5]),
            "attr_t": rnd.choice([69, 71, 67, 5]), "mask_t": rnd.choice([0, 0, 0, 0x38]),
            "blocks": blocks, "calls": calls}


def spec_offset(line, col):
    return ((line & 0xC0) << 5) + ((line & 7) << 8) + ((line & 0x38) << 2) + col


def spec_line_col(off):
    return (off >> 11) * 64 + ((off >> 5) & 7) * 8 + ((off >> 8) & 7), off & 31


def model_calls(case, bg, maps):
    """SPRITE's calls on a model of the screen: the lit pixels as bytes at
    the Spectrum's offsets, and each pixel's logical colour."""
    bits = bytearray(bg[:6144])
    attrs_now = bytearray(bg[6144:6912])
    colour = [[0] * 256 for _ in range(192)]
    for line in range(192):
        for x in range(256):
            if bits[spec_offset(line, x >> 3)] & (0x80 >> (x & 7)):
                colour[line][x] = maps[line // 8][bg[6144 + (line // 8) * 32 + (x >> 3)] & 7]
    for n in case["calls"]:
        gfx, x, y, rows, width, mode, battr = case["blocks"][n]
        ink = (battr if mode == 0 else case["attr_p"] if mode == 1 else case["attr_t"]) & 7
        door = any(lo <= gfx < hi for lo, hi in DOORS)
        shift, ncells = x & 7, width + (1 if x & 7 else 0)
        for r in range(rows):
            row = list(GFX[gfx + r * width:gfx + (r + 1) * width]) + [0]
            v = int.from_bytes(bytes(row), "big") >> shift
            shifted = v.to_bytes(width + 1, "big")
            base = spec_offset(175 - y + r, x >> 3)
            for i in range(ncells):
                # the row's attributes first, as SPRITE does (each from the
                # screen address's low byte and its third)
                off = base + i
                aa = (off >> 11) * 256 + (off & 255)
                old = attrs_now[aa]
                if mode == 0:
                    new = battr if old == case["attr_p"] else old
                elif mode == 1:
                    new = case["attr_p"] if old == battr else old
                else:
                    new = (old & case["mask_t"]) | (case["attr_t"] & ~case["mask_t"] & 255)
                attrs_now[aa] = new
            for i in range(ncells):
                off = base + i
                assert off < 6144, "into the attributes"
                line, col = spec_line_col(off)
                b = shifted[i]
                for p in range(8):
                    if b & (0x80 >> p):
                        px = col * 8 + p
                        was = bits[off] & (0x80 >> p)
                        bits[off] ^= 0x80 >> p
                        if was:
                            colour[line][px] = 0
                        else:
                            scenery = bg[spec_offset(line, col)] & (0x80 >> p)
                            home = maps[line // 8][bg[6144 + (line // 8) * 32 + col] & 7]
                            own = maps[line // 8][ink]
                            if door:
                                # (a door: the colour of its cell's ink, after this call's attributes)
                                own = maps[line // 8][attrs_now[(line // 8) * 32 + col] & 7]
                            colour[line][px] = home if scenery else own
    return bits, colour


def mode1_colours(colour):
    mem = bytearray(0x3000)
    for line in range(192):
        for x in range(0, 256, 4):
            v = 0
            for p in range(4):
                c = colour[line][x + p]
                v |= ((c >> 1) & 1) << (7 - p) | (c & 1) << (3 - p)
            mem[(line // 8) * 512 + (x // 8) * 16 + (8 if x & 4 else 0) + (line & 7)] = v
    return mem


def run_original(snap, case):
    spec = Spectrum(snap)
    m = spec.mem
    attr = 71 if case["outdoors"] else 5
    m[ATTR_P], m[MASK_P], m[P_FLAG] = attr, 0, 0
    steps = [3435]
    run_routine(spec, 3435)
    if case["outdoors"]:
        assert run_routine(spec, 55565)
        p = LAND_MAP + 32 * case["scene"]
        m[ATTR_P] = LAND_ATTR | 5
        m[23296], m[23297] = p & 255, p >> 8
        assert run_routine(spec, 57228)
    else:
        assert run_routine(spec, 55569)
        m[23296], m[23297] = case["scene"], 5
        assert run_routine(spec, 45710)
    del steps
    bg = bytes(m[16384:16384 + 6912])
    m[ATTR_P], m[ATTR_T], m[MASK_T], m[P_FLAG] = case["attr_p"], case["attr_t"], case["mask_t"], 0
    for n, (gfx, x, y, rows, width, mode, battr) in enumerate(case["blocks"]):
        a = BLOCKS + 8 * n
        m[a:a + 8] = [gfx & 255, gfx >> 8, x, y, rows, width, mode, battr]
    for n in case["calls"]:
        a = BLOCKS + 8 * n
        spec.sim.registers[H], spec.sim.registers[L] = a >> 8, a & 255
        assert run_routine(spec, SPRITE), "SPRITE didn't return"
    return bg, bytes(m[16384:16384 + 6912])


GFX = None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["gen", "cmp"])
    ap.add_argument("--snap", default="build/cauldron.z80")
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--png")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if args.what == "gen":
        rnd = random.Random(args.seed)
        cases = [gen_case(rnd) for _ in range(args.count)]
        json.dump(cases, open(f"{OUT}/cases.json", "w"))
        for i, case in enumerate(cases):
            bg, scr = run_original(args.snap, case)
            open(f"{OUT}/case_{i:03d}_bg.scr", "wb").write(bg)
            open(f"{OUT}/case_{i:03d}.scr", "wb").write(scr)
        print(f"{len(cases)} cases in {OUT}")
        return 0
    global GFX
    m = load(args.snap)
    GFX = m
    cases = json.load(open(f"{OUT}/cases.json"))
    bad = 0
    for i, case in enumerate(cases):
        cells = land_cells(m, case["scene"]) if case["outdoors"] else room_cells(m, case["scene"])
        lower, phys = colour_map(ink_counts(cells))
        maps = row_maps(case["outdoors"], lower)
        scr = open(f"{OUT}/case_{i:03d}.scr", "rb").read()
        bg = open(f"{OUT}/case_{i:03d}_bg.scr", "rb").read()
        bits, colour = model_calls(case, bg, maps)
        if bytes(bits) != scr[:6144]:
            print(f"case {i}: the model's lit pixels aren't the original's")
            bad += 1
            continue
        want = mode1_colours(colour)
        got = open(f"{OUT}/bbc_{i:03d}.bin", "rb").read()
        diff = sum(a != b for a, b in zip(got[:0x3000], want))
        adiff = sum(a != b for a, b in zip(got[0x3000:0x3300], scr[6144:]))
        if diff or adiff:
            bad += 1
            print(f"case {i}: {diff} screen bytes and {adiff} attributes differ: {json.dumps(case)}")
            if args.png:
                from PIL import Image
                os.makedirs(args.png, exist_ok=True)
                rp = rows_phys(case["outdoors"], phys)
                pair = Image.new("RGB", (520, 192))
                pair.paste(image(want, rp), (0, 0))
                pair.paste(image(got[:0x3000], rp), (264, 0))
                pair.resize((1040, 384), Image.NEAREST).save(f"{args.png}/case_{i:03d}.png")
    print("spritecases:", "all match" if not bad else f"{bad} differ", f"({len(cases)} cases)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
