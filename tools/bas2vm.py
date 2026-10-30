#!/usr/bin/env python3
"""Compile the original's BASIC to bytecode for the port's interpreter
(src/vm.6502, decision 10).

    .venv/bin/python tools/bas2vm.py [--snap build/cauldron.z80] [--out build/logic.6502]
                                     [--ops build/vmops.6502]

The original is an integer BASIC program compiled to Z80; tools/decompile.py
recovers each statement as expression trees whose meaning it checks
against the Z80 running them. This compiles the same trees to a small
stack machine's code: words on a stack, the original's operators, and its
memory as the original addresses it (PEEK and POKE translate at run time:
src/vm.6502's vm_xlat), with short forms for the variables. Every
statement starts at a label L<its original address>, so GOTO, GOSUB,
RETURN and NEXT go where the original's do.

--ops writes the opcodes' numbers and the interpreter's dispatch table,
from OPS below, so the two can't disagree.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decompile as D  # noqa: E402

VARS, VARS_END = 41015, 41575
SLOTS, SLOTS_END = 24603, 24759
BLOCKS, BLOCKS_END = 24759, 24759 + 64
FOR_VARS = 41277        # rt_next's base: FOR variables are words from here

# The operations, in opcode order: (name, operand bytes). Each runs
# src/vm.6502's op_<name>.
OPS = [
    ("pushb", 1), ("pushw", 2), ("load", 1), ("loadh", 1), ("store", 1), ("storeh", 1),
    ("ldw", 2), ("stw", 2), ("ldb", 2), ("stb", 2),
    ("peek", 0), ("poke", 0), ("dpeek", 0), ("dpoke", 0), ("elem", 2),
    ("add", 0), ("sub", 0), ("mul", 0), ("div", 0), ("mod", 0), ("and", 0), ("or", 0),
    ("eq", 0), ("ne", 0), ("lt", 0), ("gt", 0), ("le", 0), ("ge", 0),
    ("neg", 0), ("not", 0), ("abs", 0), ("sgn", 0), ("lo", 0), ("hi", 0),
    ("jz", 2), ("jnz", 2), ("jmp", 2), ("call", 2), ("ret", 0),
    ("next", 2), ("forto", 3), ("drop", 0),
    ("sprite", 0), ("usr", 0), ("rnd", 0), ("inkey", 0), ("in", 0), ("attr", 0), ("point", 0),
    ("chan", 0), ("out", 0), ("str", 0), ("num", 0), ("temps", 0), ("perm", 0), ("cls", 0),
    ("pause", 0), ("halt", 0), ("wait", 2), ("beeper", 0), ("beep", 0),
]
OPCODE = {name: n for n, (name, _) in enumerate(OPS)}
STACK_MAX = 16          # src/vm.6502's stack: compile() checks the depth

# The system variables the program uses, and where the port keeps them.
SYSVARS = {
    23563: "rnd_seed", 23564: "rnd_seed+1", 23672: "frames", 23673: "frames+1",
    23296: "prbuf", 23297: "prbuf+1", 23606: "chars", 23607: "chars+1",
    23693: "attr_p", 23695: "attr_t", 23728: "stick_res", 23729: "stick_res+1",
}


class Unsupported(Exception):
    pass


def port_place(a):
    """The port's address (an assembler expression) for the original's
    constant address a, or None if only the run-time translation knows."""
    if VARS <= a < VARS_END:
        return f"bv+{a - VARS}"
    if SLOTS <= a < SLOTS_END:
        return f"bslots+{a - SLOTS}"
    if BLOCKS <= a < BLOCKS_END:
        return f"sprite_blocks+{a - BLOCKS}"
    return SYSVARS.get(a)


class Compiler:
    def __init__(self, mem):
        self.mem = mem
        self.dec = D.Decompiler(mem)
        self.dec.run()
        D.find_arrays(self.dec.stmts)
        self.out = []           # assembler lines
        self.code = []          # the current statement's: (op, operand strings)
        self.depth = 0
        self.max_depth = 0
        self.size = 0

    # --------------------------------------------------------------- emitting

    def op(self, name, *args, pop=0, push=0):
        self.code.append((name, args))
        self.depth -= pop
        if self.depth < 0:
            raise Unsupported("stack underflow")
        self.depth += push
        self.max_depth = max(self.max_depth, self.depth)

    def flush(self):
        for name, args in self.code:
            parts = [f"OP_{name.upper()}"]
            for a in args:
                parts.append(a)
            n = OPS[OPCODE[name]][1]
            self.size += 1 + n
            if n == 0:
                self.out.append(f"    EQUB OP_{name.upper()}")
            elif n == 1:
                self.out.append(f"    EQUB OP_{name.upper()}, {args[0]}")
            elif n == 2:
                self.out.append(f"    EQUB OP_{name.upper()} : EQUW {args[0]}")
            else:
                self.out.append(f"    EQUB OP_{name.upper()}, {args[0]} : EQUW {args[1]}")
        self.code = []

    # --------------------------------------------------------------- expressions

    def push_const(self, v):
        v &= 0xFFFF
        if v < 256:
            self.op("pushb", str(v), push=1)
        else:
            self.op("pushw", str(v), push=1)

    def load_word(self, a):
        """Push the word at the original's constant address a."""
        if VARS <= a < VARS_END:
            i = (a - VARS) // 2
            if (a - VARS) % 2:
                raise Unsupported(f"odd variable address {a}")
            self.op("load" if i < 256 else "loadh", str(i & 255), push=1)
            return
        p = port_place(a)
        if p is None:
            self.push_const(a)
            self.op("dpeek", pop=1, push=1)
            return
        self.op("ldw", p, push=1)

    def expr(self, e):
        e = D.simplify(e)
        k = e[0]
        if k == "n":
            self.push_const(e[1])
        elif k == "c8":
            self.push_const(e[1])
        elif k == "v":
            self.load_word(e[1])
        elif k == "elemaddr":
            self.expr(e[2])
            self.op("elem", str(e[1]), pop=1, push=1)
        elif k == "blockaddr":
            self.expr(e[1])
            self.push_const(8)
            self.op("mul", pop=2, push=1)
            self.push_const(BLOCKS)
            self.op("add", pop=2, push=1)
        elif k == "dpeek":
            a = D.simplify(e[1])
            if D.const(a):
                self.load_word(a[1])
            else:
                self.expr(a)
                self.op("dpeek", pop=1, push=1)
        elif k == "bin":
            op = {"+": "add", "-": "sub", "*": "mul", "/": "div", "AND": "and", "OR": "or", "=": "eq",
                  "<>": "ne", "<": "lt", ">": "gt", "<=": "le", ">=": "ge"}[e[1]]
            self.expr(e[2])
            self.expr(e[3])
            self.op(op, pop=2, push=1)
        elif k == "mod":
            self.expr(e[1])
            self.expr(e[2])
            self.op("mod", pop=2, push=1)
        elif k == "un":
            op = e[1]
            if op == "PEEK":
                a = D.simplify(e[2])
                if D.const(a) and port_place(a[1]):
                    self.op("ldb", port_place(a[1]), push=1)
                    return
                self.expr(a)
                self.op("peek", pop=1, push=1)
                return
            self.expr(e[2])
            self.op({"NEG": "neg", "NOT": "not", "ABS": "abs", "SGN": "sgn"}[op], pop=1, push=1)
        elif k == "lo":
            self.expr(e[1])
            self.op("lo", pop=1, push=1)
        elif k == "hi":
            self.expr(e[1])
            self.op("hi", pop=1, push=1)
        elif k == "fx":
            t = e[2]
            if t[0] == "inkey":
                self.op("inkey", push=1)
                return
            self.expr(t[2])
            self.op({"RND": "rnd", "USR": "usr", "IN": "in"}[t[1]], pop=1, push=1)
        elif k == "fn":
            self.expr(e[2])
            self.expr(e[3])
            self.op({"ATTR": "attr", "POINT": "point"}[e[1]], pop=2, push=1)
        else:
            raise Unsupported(f"expression {k}")

    # --------------------------------------------------------------- statements

    def store(self, dst, val, word):
        d = D.simplify(dst)
        if D.const(d):
            a = d[1]
            if word and VARS <= a < VARS_END and (a - VARS) % 2 == 0:
                self.expr(val)
                i = (a - VARS) // 2
                self.op("store" if i < 256 else "storeh", str(i & 255), pop=1)
                return
            p = port_place(a)
            if p and (not word or port_place(a + 1)):
                self.expr(val)
                self.op("stw" if word else "stb", p, pop=1)
                return
        self.expr(val)
        self.expr(d)
        self.op("dpoke" if word else "poke", pop=2)

    def event(self, ev):
        k = ev[0]
        if k == "let":
            d = D.simplify(ev[1])
            # A FOR's limit, step and loop-back address: the last is the
            # statement after, as the port's label.
            if (D.const(d) and SLOTS <= d[1] < SLOTS_END and (d[1] - SLOTS) % 6 == 4
                    and ev[2][0] == "n" and D.CODE_START <= ev[2][1] < D.CODE_END):
                self.op("forto", str(d[1] - 4 - SLOTS), f"L{ev[2][1]}")
                return
            self.store(ev[1], ev[2], True)
        elif k == "poke":
            v = ev[2]
            self.store(ev[1], v[1] if v[0] == "lo" else v, False)
        elif k == "if":
            self.expr(ev[2])
            self.op("jnz" if ev[1] == "NZ" else "jz", f"L{ev[3]}", pop=1)
        elif k == "goto":
            self.op("jmp", f"L{ev[1]}")
        elif k == "gosub":
            self.op("call", f"L{ev[1]}")
        elif k == "return":
            self.op("ret")
        elif k == "call":
            self.expr(ev[1])
            self.op("drop", pop=1)
        elif k == "sprite":
            blk = D.in_block(D.simplify(ev[1]))
            if not blk or blk[1]:
                raise Unsupported("sprite block")
            self.expr(blk[0][1])
            self.op("sprite", pop=1)
        elif k in ("chan", "out", "num", "pause"):
            self.expr(ev[1])
            self.op(k, pop=1)
        elif k == "str":
            self.expr(ev[1])
            self.expr(ev[2])
            self.op("str", pop=2)
        elif k in ("temps", "perm", "cls", "halt"):
            self.op(k)
        elif k == "border":
            pass                            # the BBC's border is black
        elif k == "beeper":
            self.expr(ev[1])
            self.expr(ev[2])
            self.op("beeper", pop=2)
        elif k == "beep":
            dur = ev[1]
            if dur[0] != "fp" or dur[1] != "/":
                raise Unsupported("BEEP's duration")
            self.expr(ev[2])
            self.op("beep", pop=1)
        else:
            raise Unsupported(f"event {k}")

    def statement(self, s):
        if s.kind == "next":
            i = (s.var - FOR_VARS) // 2
            if not 0 <= i < 256 or (s.var - FOR_VARS) % 2:
                raise Unsupported(f"FOR variable {s.var}")
            self.op("next", str(i | (s.slot - SLOTS) << 8))
        elif s.kind == "wait":
            self.op("wait", s.text.split()[1])
        elif s.kind == "raw":
            raise Unsupported(f"raw statement at {s.addr}")
        else:
            for ev in s.events:
                self.event(ev)
                if self.depth:
                    raise Unsupported("values left on the stack")

    def compile(self):
        bad = []
        for s in self.dec.stmts:
            self.out.append(f".L{s.addr}")
            self.depth = 0
            try:
                self.statement(s)
                self.flush()
            except (Unsupported, KeyError) as exc:
                self.code = []
                self.out.append(f"    EQUB OP_BAD  ; {exc}")
                bad.append((s.addr, str(exc)))
        return bad


def write_ops(path):
    with open(path, "w") as f:
        f.write("\\ Made by tools/bas2vm.py: the interpreter's opcodes and dispatch table.\n")
        for n, (name, _) in enumerate(OPS):
            f.write(f"OP_{name.upper()} = {n}\n")
        f.write(f"OP_BAD = {len(OPS)}\n")
        f.write(f"VM_OPS = {len(OPS)}\n")
        f.write(f"VM_STACK = {STACK_MAX}\n")


def write_table(path):
    with open(path, "w") as f:
        f.write("\\ Made by tools/bas2vm.py: each opcode's handler, less 1 (for RTS).\n")
        f.write("\\ (vm.6502's dispatch lands on any of them: ZA_CANJUMP's list.)\n")
        f.write(".vm_lo\n")
        for name, _ in OPS + [("bad", 0)]:
            f.write(f"    EQUB LO(op_{name} - 1)\n")
        f.write(".vm_hi\n")
        for name, _ in OPS + [("bad", 0)]:
            f.write(f"    EQUB HI(op_{name} - 1)\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snap", default="build/cauldron.z80")
    ap.add_argument("--out", default="build/logic.6502")
    ap.add_argument("--ops", default="build/vmops.6502")
    ap.add_argument("--table", default="build/vmtable.6502")
    args = ap.parse_args()
    c = Compiler(D.load_memory(args.snap))
    bad = c.compile()
    if c.max_depth > STACK_MAX:
        bad.append((0, f"the stack reaches {c.max_depth}"))
    with open(args.out, "w") as f:
        f.write("\\ Made by tools/bas2vm.py from the original's BASIC: don't edit.\n")
        f.write("\n".join(c.out) + "\n")
    write_ops(args.ops)
    write_table(args.table)
    with open(os.path.join(os.path.dirname(args.table), "vmjump.6502"), "w") as f:
        f.write("\\ Made by tools/bas2vm.py: where vm.6502's RTS dispatch may land.\n")
        f.write("    ZA_CANJUMP " + ", ".join(f"op_{name}" for name, _ in OPS + [("bad", 0)]) + "\n")
    print(f"{args.out}: {c.size} bytes of bytecode; the stack reaches {c.max_depth}; "
          f"{len(bad)} statements unsupported")
    for a, why in bad[:30]:
        print(f"  {a}: {why}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
