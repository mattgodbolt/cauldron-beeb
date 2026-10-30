#!/usr/bin/env python3
"""What the original's BASIC reads and writes outside its variables, in
play: the regions src/vmxlat.6502 must give a place.

    .venv/bin/python tools/zxaccess.py [--seeds 1-2] [--passes N]

Plays as tools/zxranges.py does (outdoors, and through each door), and
records the address of every PEEK (the library's 25048, HL) and DPEEK of
a computed address, and every byte that changes outside the variables,
the system variables, the stack and the screen (POKEs, and what the
machine code writes). Prints them as runs of addresses.
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skoolkit.simutils import H, L, PC, T  # noqa: E402
import zxranges as R  # noqa: E402

PEEK = 25048


def runs(addrs):
    out = []
    for a in sorted(addrs):
        if out and a <= out[-1][1] + 8:
            out[-1][1] = a
        else:
            out.append([a, a])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", default="1-2")
    ap.add_argument("--passes", type=int, default=150)
    args = ap.parse_args()
    a, _, b = args.seeds.partition("-")
    peeks, writes = set(), set()

    def play(spec, rnd, until_game_over):
        m = spec.mem
        regs = spec.sim.registers
        before = bytes(m[41575:65536])
        n = 0
        held, left = [], 0
        end = regs[T] + args.passes * 10 * R.FRAME
        while n < args.passes and regs[T] < end:
            pc = regs[PC]
            if pc == PEEK:
                peeks.add(regs[H] << 8 | regs[L])
            if pc in R.LOOPS:
                n += 1
                left -= 1
                if left <= 0:
                    for k in held:
                        spec.key(k, False)
                    held = rnd.sample(R.KEYS, rnd.choice([0, 1, 1, 2, 2, 3]))
                    for k in held:
                        spec.key(k, True)
                    left = rnd.randrange(1, 12)
            elif pc == R.GAME_OVER and until_game_over:
                break
            spec.sim.trace(pc, None, 1, 0, 1, None, None, None, None, None)
        after = bytes(m[41575:65536])
        writes.update(41575 + i for i in range(len(after)) if after[i] != before[i])

    for seed in range(int(a), int(b or a) + 1):
        spec, rnd = R.start(seed)
        play(spec, rnd, True)
        for door in range(2, 7):
            spec, rnd = R.start(seed * 10 + door)
            spec.frames(400)
            for k in R.KEYS_HELD:
                R.poke(spec.mem, k, 1)
            target = R.w(spec.mem, R.DOOR_AT + 2 * (door - 1))
            spec.key("CAPS", True)
            for _ in range(40):
                spec.run_tstates(69888 * 50, stop=30492)
                R.poke(spec.mem, R.SCROLL, target); R.poke(spec.mem, R.X, 40); R.poke(spec.mem, R.Y, 23)
                if spec.run_tstates(69888 * 2, stop=35597) == 35597:
                    break
            spec.key("CAPS", False)
            play(spec, rnd, False)
    print("PEEKed:", " ".join(f"{x}-{y}" for x, y in runs(peeks)))
    print("written:", " ".join(f"{x}-{y}" for x, y in runs(writes)))


if __name__ == "__main__":
    sys.exit(main())
