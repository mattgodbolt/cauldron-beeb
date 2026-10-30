#!/usr/bin/env python3
"""The statements of the original's BASIC a pass runs most: which the
port compiles to native code (decision 10).

    .venv/bin/python tools/zxhot.py [--scenarios a,b] [--out build/hot.json]

Plays tests/scenarios.txt's scenarios on the original (as tools/zxpass.py
does) and counts each statement's runs a pass. Writes {address: runs a
pass}, the scenarios' largest, for tools/bas2vm.py's --hot.
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skoolkit.simutils import PC  # noqa: E402
from zxpass import AFTER_RANDOMIZE, HOUSE, KEYS, LOOPS, SEED, Spectrum, scenarios  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenarios", default="fly_right,fire,door2,door4")
    ap.add_argument("--out", default="build/hot.json")
    args = ap.parse_args()
    stmts = set()
    for line in open("build/cauldron.bas"):
        m = re.match(r"^(\d+)[ ~]", line)
        if m:
            stmts.add(int(m.group(1)))
    hot = collections.Counter()
    for name in args.scenarios.split(","):
        seed, passes = scenarios()[name]
        spec = Spectrum("build/cauldron.z80")
        m, sim, regs = spec.mem, spec.sim, spec.sim.registers

        def run_until(stops):
            while True:
                sim.trace(regs[PC], None, 1, 0, 1, None, None, None, None, None)
                if regs[PC] in stops:
                    return
        run_until({AFTER_RANDOMIZE})
        m[SEED], m[SEED + 1] = seed & 255, seed >> 8
        spec.key("4", True)
        run_until({HOUSE})
        spec.key("4", False)
        counts = collections.Counter()
        held, n = [], 0
        for keys, pokes in passes:
            while True:
                pc = regs[PC]
                if pc in stmts:
                    counts[pc] += 1
                sim.trace(pc, None, 1, 0, 1, None, None, None, None, None)
                if regs[PC] in LOOPS:
                    break
            n += 1
            for a, v in pokes:
                v = (m[int(v[1:])] | m[int(v[1:]) + 1] << 8) if v.startswith("@") else int(v)
                m[a], m[a + 1] = v & 255, (v >> 8) & 255
            for k in held:
                spec.key(KEYS[k], False)
            held = list(keys)
            for k in held:
                spec.key(KEYS[k], True)
        for a, c in counts.items():
            hot[a] = max(hot[a], c / n)
    json.dump({str(a): round(c, 2) for a, c in hot.most_common()}, open(args.out, "w"), indent=0)
    top = hot.most_common()
    print(f"{len(top)} statements run; a pass runs {sum(c for _, c in top):.0f} at most")
    for a, c in top[:25]:
        print(f"  {a}: {c:.1f}")


if __name__ == "__main__":
    sys.exit(main())
