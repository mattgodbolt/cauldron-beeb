#!/usr/bin/env python3
"""The original's side of make passes: each scenario's variables at the
top of every main-loop pass.

    .venv/bin/python tools/zxpass.py [scenario ...] [--out build/passes]

For each scenario in tests/scenarios.txt: from the game's entry, RND's
seed set to the scenario's just after RANDOMIZE (25606), 4 held at the
menu until the house scene starts (26691), then at the top of each pass
(30489 above ground, 35688 below) the variables (41015-41574) are
noted and the pass's keys held. Writes build/passes/<name>.zx.json: a
list of the variable blocks as hex, a pass each.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skoolkit.simutils import PC  # noqa: E402
from zx import Spectrum  # noqa: E402

FRAME = 69888

VARS, VARS_END = 41015, 41575
SEED = 23563
AFTER_RANDOMIZE = 25606
HOUSE = 26691
LOOPS = (30489, 35688)
KEYS = {"L": "CAPS", "R": "Z", "U": "C", "D": "X", "F": "V"}
FRAME = 69888


def scenarios(path="tests/scenarios.txt"):
    out = {}
    for line in open(path):
        line = line.split("#")[0].strip()
        if not line:
            continue
        name, seed, *steps = line.split()
        passes = []
        for st in steps:
            keys, _, n = st.partition("*")
            passes += [keys.replace("-", "")] * int(n or 1)
        out[name] = (int(seed), passes)
    return out


def run_until(spec, stops, limit=50_000_000):
    """Step until PC is one of stops (after at least one instruction)."""
    sim = spec.sim
    regs = sim.registers
    for _ in range(limit):
        sim.trace(regs[PC], None, 1, 0, 1, None, None, None, None, None)
        if regs[PC] in stops:
            return regs[PC]
    raise RuntimeError(f"never reached {stops}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*")
    ap.add_argument("--snap", default="build/cauldron.z80")
    ap.add_argument("--out", default="build/passes")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    for name, (seed, passes) in scenarios().items():
        if args.names and name not in args.names:
            continue
        spec = Spectrum(args.snap)
        m = spec.mem
        run_until(spec, {AFTER_RANDOMIZE})
        m[SEED], m[SEED + 1] = seed & 255, seed >> 8
        spec.key("4", True)
        run_until(spec, {HOUSE})
        spec.key("4", False)
        blocks = []
        held = []
        for keys in passes + [""]:
            run_until(spec, set(LOOPS))
            blocks.append(bytes(m[VARS:VARS_END]).hex())
            for k in held:
                spec.key(KEYS[k], False)
            held = list(keys)
            for k in held:
                spec.key(KEYS[k], True)
        json.dump(blocks, open(f"{args.out}/{name}.zx.json", "w"))
        print(f"{name}: {len(blocks)} passes")


if __name__ == "__main__":
    sys.exit(main())
