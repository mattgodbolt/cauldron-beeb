#!/usr/bin/env python3
"""The range of every variable of the original's BASIC in play: what
the port's compiled logic may keep in a byte (decision 10).

    .venv/bin/python tools/zxranges.py [--seeds 1-8] [--passes N] [--out build/ranges.json]

Plays the original with random keys, from the start of a game, outdoors
and (by putting the witch at a door with its key, as the decompiler's
exploration did) underground in each door's caverns, for --passes main
loop passes each. After every statement of the BASIC it notes the
signed range of each variable word (41015-41574) that changed, and of
the FOR slots (24603-24758). Writes {address: [min, max]} for every
word ever written, merged with what --out held before.
"""
import argparse
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skoolkit.simutils import PC  # noqa: E402
from zx import Spectrum  # noqa: E402

VARS, VARS_END = 41015, 41575
SLOTS, SLOTS_END = 24603, 24759
LOOPS = (30489, 35688)      # the tops of the main loop and the underground one
FRAME = 69888
GAME_OVER = 40156
KEYS = ["CAPS", "Z", "C", "X", "V"]   # left, right, up, down, fire
DOOR_AT, KEYS_HELD = 41249, (41239, 41241, 41243, 41245, 41247)
SCROLL, X, Y = 41329, 41277, 41365


def w(m, a):
    return m[a] | m[a + 1] << 8


def poke(m, a, v):
    m[a], m[a + 1] = v & 255, (v >> 8) & 255


def statements():
    out = set()
    for line in open("build/cauldron.bas"):
        mm = re.match(r"^(\d+)[ ~]", line)
        if mm:
            out.add(int(mm.group(1)))
    return out


class Ranges:
    def __init__(self, known):
        self.r = {int(k): v for k, v in known.items()}

    def note(self, m, lo, hi, prev):
        cur = bytes(m[lo:hi])
        if cur != prev:
            for a in range(lo, hi, 2):
                o = a - lo
                if cur[o:o + 2] != prev[o:o + 2]:
                    v = cur[o] | cur[o + 1] << 8
                    v = v - 65536 if v & 0x8000 else v
                    r = self.r.setdefault(a, [v, v])
                    r[0], r[1] = min(r[0], v), max(r[1], v)
        return cur


def run(spec, stmts, ranges, rnd, passes, until_game_over=False):
    m = spec.mem
    sim = spec.sim
    regs = sim.registers
    pv = bytes(m[VARS:VARS_END])
    ps = bytes(m[SLOTS:SLOTS_END])
    held, left = [], 0
    n = 0
    from skoolkit.simutils import T
    end = regs[T] + passes * 10 * FRAME       # (a pass is under 10 frames, scrolls aside)
    while n < passes and regs[T] < end:
        pc = regs[PC]
        if pc in stmts:
            pv = ranges.note(m, VARS, VARS_END, pv)
            ps = ranges.note(m, SLOTS, SLOTS_END, ps)
            if pc in LOOPS:
                n += 1
                left -= 1
                if left <= 0:
                    for k in held:
                        spec.key(k, False)
                    held = rnd.sample(KEYS, rnd.choice([0, 1, 1, 2, 2, 3]))
                    for k in held:
                        spec.key(k, True)
                    left = rnd.randrange(1, 12)
            elif pc == GAME_OVER and until_game_over:
                return
        sim.trace(pc, None, 1, 0, 1, None, None, None, None, None)


def start(seed):
    spec = Spectrum("build/cauldron.z80")
    rnd = random.Random(seed)
    spec.frames(100 + rnd.randrange(50))
    spec.key("3", True); spec.frames(5); spec.key("3", False)
    spec.frames(50)
    spec.key("4", True); spec.frames(5); spec.key("4", False)
    return spec, rnd


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", default="1-4")
    ap.add_argument("--passes", type=int, default=400)
    ap.add_argument("--out", default="build/ranges.json")
    args = ap.parse_args()
    a, _, b = args.seeds.partition("-")
    seeds = range(int(a), int(b or a) + 1)
    known = json.load(open(args.out)) if os.path.exists(args.out) else {}
    ranges = Ranges(known)
    stmts = statements()
    for seed in seeds:
        # Outdoors, to a game over or the passes.
        spec, rnd = start(seed)
        run(spec, stmts, ranges, rnd, args.passes, until_game_over=True)
        # Underground, through each door (1 is the cottage's).
        for door in range(2, 7):
            spec, rnd = start(seed * 10 + door)
            spec.frames(400)
            for k in KEYS_HELD:
                poke(spec.mem, k, 1)
            target = w(spec.mem, DOOR_AT + 2 * (door - 1))
            spec.key("CAPS", True)
            for _ in range(40):
                spec.run_tstates(69888 * 50, stop=30492)
                poke(spec.mem, SCROLL, target); poke(spec.mem, X, 40); poke(spec.mem, Y, 23)
                if spec.run_tstates(69888 * 2, stop=35597) == 35597:
                    break
            spec.key("CAPS", False)
            run(spec, stmts, ranges, rnd, args.passes)
        print(f"seed {seed}: {len(ranges.r)} words seen", flush=True)
        json.dump({str(k): v for k, v in sorted(ranges.r.items())}, open(args.out, "w"), indent=0)
    json.dump({str(k): v for k, v in sorted(ranges.r.items())}, open(args.out, "w"), indent=0)
    bytes_ = sum(1 for lo, hi in ranges.r.values() if 0 <= lo and hi <= 255)
    print(f"{len(ranges.r)} words written; {bytes_} always 0-255")


if __name__ == "__main__":
    sys.exit(main())
