#!/usr/bin/env python3
"""Decompile Cauldron's compiled BASIC back to a BASIC-like listing.

    .venv/bin/python tools/decompile.py [--snap build/cauldron.z80] [--out build/cauldron.bas]
                                        [--map FILE ...] [--verify N]

`make bas` runs it with the execution maps in build/maps/.

Cauldron's game logic was written in integer BASIC and compiled with
Phipps Associates' BASIC compiler. The code generator is simple and
regular: every expression is built in HL, a binary operator's left operand
is moved to DE with EX DE,HL while the right one is loaded, a live DE is
spilled with PUSH DE/POP DE, and each operator is either inline (ADD
HL,DE; XOR A : SBC HL,DE) or a CALL into the runtime library at 24880-25591.
docs/research/compiler.md describes the idioms and the library.

So this tool doesn't pattern-match statements. It executes the compiled
code symbolically: the registers and the stack hold expression trees, and
each instruction the code generator uses is modelled exactly (a runtime
call marks the registers it corrupts as unknown). A statement ends at a
side effect (a store, an output, a call, a jump) that leaves the stack
empty. Anything the model can't follow (an instruction it doesn't know, a
read of an unknown register, a POP of an empty stack) is printed as raw
`Z80:` lines, from the start of the statement it was in, and the model
starts afresh after it. Nothing is guessed.

On top of that, a few fixed templates (NEXT, a HALT loop) are matched by
their exact instruction sequence, and passes over the statements merge a
FOR's four stores into one FOR, and the outputs of a PRINT into one PRINT.

It checks itself and reports, in its output and the listing's header:

- coverage: bytes of the compiled region decompiled against bytes printed
  raw (they must add up to the region);
- given execution maps (tools/zx.py --map), how much of the region ran,
  that every executed address is an instruction start, and how much of the
  executed code fell in raw lines; statements no map ran are marked;
- each statement that stores or branches, run on the Z80 (the original's
  own code, SkoolKit's simulator) from random variables and compared with
  its expression tree evaluated under a Python model of the runtime
  library (--verify N trials each).

It exits non-zero if a check fails.

Names come from tools/decompile_names.py.
"""
import argparse
import os
import re
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decompile_names as names
from skoolkit.disassembler import Disassembler
from skoolkit.snapshot import Snapshot

CODE_START = 25592   # the compiled program's first statement (24600 is JP 25592)
CODE_END = 41015     # the first variable: the program's last instruction is JP 25592 at 41012
FOR_SLOTS = (24603, 24759)   # the FOR loops' limit/step/address triples
SPRITE_TABLE = 24759         # 8-byte sprite parameter blocks, for 25431
VAR_START = 41015

# The runtime library. Two-operand functions take HL (left) and DE (right).
# 'clob' lists the registers left unknown afterwards ('A' always is).
BINOPS = {
    24880: ("*", "DE BC"),
    24911: ("/", "BC"),          # HL = quotient; DE = remainder (handled below)
    24980: ("=", ""),
    24989: ("<>", ""),
    24998: (">=", "DE"),
    24999: ("<=", ""),
    25008: ("<", ""),
    25023: (">", "DE"),
    25173: ("AND", ""),          # bitwise, 16 bits
    25180: ("OR", ""),           # bitwise, 16 bits
}
BINFNS = {
    25073: ("POINT", "DE BC"),    # POINT (x=HL, y=DE)
    25089: ("ATTR", "BC"),       # ATTR (line=HL, column=DE)
    25106: ("SCREEN$", "DE BC"),  # SCREEN$ (line=HL, column=DE), as a code
}
UNOPS = {
    24972: ("NEG", ""),
    25063: ("ABS", ""),
    25187: ("NOT", ""),
    25195: ("SGN", ""),
    25048: ("PEEK", ""),
    25051: ("IN", "BC"),
    25205: ("USR", "DE BC"),
    25214: ("RND", "BC"),        # 0 .. HL-1; see compiler.md for the generator
    25212: ("CODE", ""),         # just RET: CODE INKEY$ costs nothing
}
SIDE_EFFECT_FNS = {"USR", "RND", "INKEY$", "IN"}

# ROM routines and library routines called as statements.
ROM_STMTS = {
    3435: "CLS",
    3405: "TEMPS",               # end of a PRINT: temporary colours back to permanent
    7341: "PERM",                # after INK/PAPER... as a statement: make them permanent
}

PRINT_CTRL = {16: "INK", 17: "PAPER", 18: "FLASH", 19: "BRIGHT", 20: "INVERSE", 21: "OVER"}

CALC_OPS = {3: "-", 4: "*", 5: "/", 15: "+"}


# ---------------------------------------------------------------- memory, decoding

def load_memory(path):
    snap = Snapshot.get(path)
    ram = list(snap.ram(-1))
    if len(ram) == 49152:
        ram = [0] * 16384 + ram
    return ram


class Ins:
    def __init__(self, addr, op, data):
        self.addr = addr
        self.op = op
        self.data = list(data)
        self.len = len(self.data)

    @property
    def end(self):
        return self.addr + self.len

    def __repr__(self):
        return f"{self.addr} {self.op}"


def disassemble(mem, start, end):
    """Linear disassembly, with the calculator's literal bytes after RST 40
    taken as one pseudo-instruction ('CALC b1,b2,...')."""
    cfg = SimpleNamespace(asm_hex=False, asm_lower=False, defb_size=8, defm_size=66,
                          defw_size=1, handle_rst=False, imaker=Ins, wrap=False, opcodes="")
    dis = Disassembler(mem, cfg)
    out = []
    a = start
    while a < end:
        ins = dis.disassemble(a, a + 1, "n")[0]
        if ins.op == "RST 40":
            n = a + 1
            while mem[n] != 0x38 and n < a + 32:
                n += 1
            data = mem[a:n + 1]
            ins = Ins(a, "CALC " + ",".join(str(b) for b in data[1:]), data)
        out.append(ins)
        a = ins.end
    return out


# Pseudo-instructions for fixed multi-instruction moves.
MERGES = [
    (("LD A,(HL)", "INC HL", "LD H,(HL)", "LD L,A"), "LDW HL,(HL)"),
    (("LD (HL),E", "INC HL", "LD (HL),D"), "STW (HL),DE"),
    (("LD B,H", "LD C,L"), "LD BC,HL"),
]


def merge(instrs, labels):
    out = []
    i = 0
    while i < len(instrs):
        for seq, name in MERGES:
            n = len(seq)
            chunk = instrs[i:i + n]
            if (len(chunk) == n and all(c.op == s for c, s in zip(chunk, seq))
                    and not any(c.addr in labels for c in chunk[1:])):
                m = Ins(chunk[0].addr, name, [b for c in chunk for b in c.data])
                m.parts = chunk
                out.append(m)
                i += n
                break
        else:
            out.append(instrs[i])
            i += 1
    return out


NUM = r"(\d+)"


def find_labels(instrs):
    """Every address something jumps or calls to, or a FOR stores as its
    loop-back address. Returns {target: [(from, kind)]}."""
    labels = {}
    prev = None
    for ins in instrs:
        m = re.match(r"(JP|JR|CALL)(?: (N?Z|N?C|P|M|PE|PO),| )" + NUM + "$", ins.op)
        if m:
            kind = {"CALL": "GOSUB"}.get(m.group(1), "GOTO" if not m.group(2) else "IF")
            labels.setdefault(int(m.group(3)), []).append((ins.addr, kind))
        m = re.match(r"LD \(" + NUM + r"\),HL$", ins.op)
        if m and prev is not None and FOR_SLOTS[0] <= int(m.group(1)) < FOR_SLOTS[1]:
            mm = re.match(r"LD HL," + NUM + "$", prev.op)
            if mm and int(mm.group(1)) == ins.end:
                labels.setdefault(ins.end, []).append((ins.addr, "FOR"))
        prev = ins
    return labels


# ---------------------------------------------------------------- expressions
# Trees are tuples:
#   ('n', v)                 a constant (16 bits)
#   ('v', addr)              the word variable at addr
#   ('bin', op, a, b)        a binary operator
#   ('un', op, a)            NEG, NOT, ABS, SGN; or a one-argument function
#   ('fn', name, a, b)       a two-argument function (POINT, ATTR, SCREEN$)
#   ('inkey',)               INKEY$ as a code (0 if no key)
#   ('mod', a, b)            the remainder the divide leaves in DE
#   ('dpeek', a)             the word at address a
#   ('lo', e), ('hi', e)     A from L or H
#   ('c8', v)                A loaded with a constant
#   ('fp', ...)              a value on the ROM calculator's stack
# Each side-effecting call (USR, RND, INKEY$, IN) is wrapped as
# ('fx', id, tree) so a dropped one can still be reported.

class Fail(Exception):
    pass


def const(e):
    return e[0] == "n"


def s16(v):
    return v - 65536 if v >= 32768 else v


def simplify(e):
    """Canonical forms: arrays, sprite blocks, folded constants."""
    if e[0] == "bin":
        a, b = simplify(e[2]), simplify(e[3])
        op = e[1]
        # base + 2*(i-1): an array element's address
        for x, y in ((a, b), (b, a)):
            if (op == "+" and const(y) and x[0] == "bin" and x[1] == "*" and x[3] == ("n", 2)
                    and x[2][0] == "bin" and x[2][1] == "-" and x[2][3] == ("n", 1)):
                return ("elemaddr", y[1], x[2][2])
            if (op == "+" and y == ("n", SPRITE_TABLE) and x[0] == "bin" and x[1] == "*"
                    and x[3] == ("n", 8)):
                return ("blockaddr", x[2])
        if op == "*" and a[0] == "bin" and a[1] == "*" and const(a[3]) and const(b):
            return ("bin", "*", a[2], ("n", (a[3][1] * b[1]) & 0xFFFF))
        return ("bin", op, a, b)
    if e[0] in ("un", "dpeek", "lo", "hi", "fx"):
        return e[:-1] + (simplify(e[-1]),)
    if e[0] in ("fn", "mod"):
        return (e[0],) + e[1:-2] + (simplify(e[-2]), simplify(e[-1]))
    return e


PREC = {"OR": 2, "AND": 3, "=": 5, "<>": 5, "<": 5, ">": 5, "<=": 5, ">=": 5,
        "+": 6, "-": 6, "*": 8, "/": 8, "MOD": 8}


# Array bases, sorted, and where the scalars start: set by find_arrays().
ARRAY_BASES = []
FIRST_SCALAR = 41277


# FOR loops' control variables, by address: the letter their slot gives.
FOR_LETTERS = {}


def for_letter(slot):
    """The compiler keeps a FOR's limit, step and loop address in a 6-byte
    slot per letter, a..z, from 24603: the slot names the variable."""
    return chr(ord("a") + (slot - FOR_SLOTS[0]) // 6)


def var_name(addr):
    if addr in names.VARS:
        return names.VARS[addr]
    if addr in FOR_LETTERS:
        return FOR_LETTERS[addr]
    if ARRAY_BASES and ARRAY_BASES[0] <= addr < FIRST_SCALAR:
        # a constant index, folded by the compiler into an address
        base = max(b for b in ARRAY_BASES if b <= addr)
        if (addr - base) % 2 == 0:
            return f"{array_name(base)}({(addr - base) // 2 + 1})"
    return f"v{addr}"


def find_arrays(stmts):
    """Every base an element address is built from."""
    bases = set(names.ARRAYS)

    def walk(e):
        if isinstance(e, tuple) and e:
            if e[0] == "elemaddr":
                bases.add(e[1])
            for x in e[1:]:
                walk(x)
    for st in stmts:
        for ev in getattr(st, "events", None) or []:
            walk(tuple(simplify(x) if isinstance(x, tuple) and x and isinstance(x[0], str) and x[0] in
                       ("bin", "un", "fn", "dpeek", "lo", "hi", "fx", "mod") else x for x in ev))
    ARRAY_BASES[:] = sorted(b for b in bases if VAR_START <= b < FIRST_SCALAR)


def addr_name(a):
    """A constant address, with the system variable's name if it has one."""
    n = names.SYSVARS.get(a)
    return f"{a} [{n}]" if n else str(a)


def array_name(base):
    return names.ARRAYS.get(base, f"a{base}")


def render(e, prec=0):
    e = simplify(e)
    return _render(e, prec)


def _render(e, prec=0):
    k = e[0]
    if k == "n":
        # Constants print unsigned, as the source most likely wrote them,
        # except -256..-1.
        v = e[1] - 65536 if e[1] >= 65280 else e[1]
        return str(v) if v >= 0 or prec < 9 else f"({v})"
    if k == "v":
        if e[1] < VAR_START and e[1] in names.SYSVARS:
            return f"DPEEK {addr_name(e[1])}"
        return var_name(e[1])
    if k == "fx":
        return _render(e[2], prec)
    if k == "bin":
        op = e[1]
        p = PREC[op]
        # Left-associative: the right operand needs brackets at equal precedence.
        s = f"{_render(e[2], p)} {op} {_render(e[3], p + 1)}"
        return f"({s})" if p < prec else s
    if k == "mod":
        s = f"{_render(e[1], 8)} MOD {_render(e[2], 9)}"
        return f"({s})" if 8 < prec else s
    if k == "un":
        op, a = e[1], e[2]
        if op == "NEG":
            s = f"-{_render(a, 9)}"
            return f"({s})" if prec > 6 else s
        if op == "NOT":
            s = f"NOT {_render(a, 4)}"
            return f"({s})" if prec > 4 else s
        if op == "CODE":
            return f"CODE {_render(a, 11)}"
        if op in ("PEEK", "USR", "IN", "RND", "ABS", "SGN"):
            if op == "PEEK" and const(a) and a[1] in names.SYSVARS:
                return f"PEEK {addr_name(a[1])}"
            if op == "USR" and const(a) and a[1] in names.USR:
                return f"USR {a[1]} [{names.USR[a[1]]}]"
            return f"{op} {_render(a, 11)}" if a[0] in ("n", "v") else f"{op}({_render(a)})"
    if k == "fn":
        return f"{e[1]}({_render(e[2])}, {_render(e[3])})"
    if k == "inkey":
        return "INKEY$"
    if k == "elemaddr":
        return f"@{array_name(e[1])}({_render(e[2])})"
    if k == "blockaddr":
        return f"@sprite({_render(e[1])})"
    if k == "dpeek":
        a = e[1]
        if a[0] == "elemaddr":
            return f"{array_name(a[1])}({_render(a[2])})"
        if const(a):
            return var_name(a[1]) if a[1] >= VAR_START else f"DPEEK {addr_name(a[1])}"
        return f"DPEEK({_render(a)})"
    if k == "lo":
        return _render(e[1], prec)
    if k == "hi":
        return f"INT({_render(e[1])}/256)"
    if k == "c8":
        return str(e[1])
    if k == "fp":
        if e[1] == "n":
            return _render(e[2], prec)
        s = f"{_render(e[2], PREC[e[1]])} {e[1]} {_render(e[3], PREC[e[1]] + 1)}"
        return f"({s})" if PREC[e[1]] < prec else s
    raise Fail(f"cannot render {e!r}")


def target(addr_e):
    """An lvalue, for a word store at the address addr_e."""
    a = simplify(addr_e)
    if a[0] == "elemaddr":
        return f"{array_name(a[1])}({_render(a[2])})"
    if const(a):
        return var_name(a[1])
    return None


def fx_ids(e, acc=None):
    if acc is None:
        acc = set()
    if isinstance(e, tuple):
        if e and e[0] == "fx":
            acc.add(e[1])
        for x in e[1:]:
            fx_ids(x, acc)
    return acc


# ---------------------------------------------------------------- the machine

UNKNOWN = None


class State:
    def __init__(self):
        self.reset()

    def reset(self):
        self.r = {"HL": UNKNOWN, "DE": UNKNOWN, "BC": UNKNOWN, "A": UNKNOWN}
        self.stack = []
        self.flags = UNKNOWN     # ('nz', e): Z set iff e == 0
        self.carry = UNKNOWN
        self.fp = []             # the ROM calculator's stack
        self.blocks = []         # pending byte/word stores into a sprite block

    def get(self, reg):
        v = self.r[reg]
        if v is UNKNOWN:
            raise Fail(f"{reg} unknown")
        return v

    def live(self):
        vals = list(self.r.values()) + self.stack
        return set().union(*(fx_ids(v) for v in vals if v is not None)) if vals else set()


class Stmt:
    """One statement: kind, the address range, and the parts to print."""

    def __init__(self, addr, end, kind, **kw):
        self.addr = addr
        self.end = end
        self.kind = kind
        self.__dict__.update(kw)
        self.text = kw.get("text", "")

    @property
    def nbytes(self):
        return self.end - self.addr


fx_counter = [0]


def fx(tree):
    fx_counter[0] += 1
    return ("fx", fx_counter[0], tree)


class Decompiler:
    def __init__(self, mem):
        self.mem = mem
        raw = disassemble(mem, CODE_START, CODE_END)
        self.labels = find_labels(raw)
        self.instrs = merge(raw, self.labels)
        self.index = {ins.addr: n for n, ins in enumerate(self.instrs)}
        self.stmts = []
        self.fx_pending = {}     # id -> (tree, first instruction address)

    # ------------------------------------------------------------ templates

    def match_next(self, i):
        """NEXT var: var += step; if (step >= 0 ? limit < var : var < limit) fall
        through, else JP (stored loop address)."""
        seq = self.instrs[i:i + 17]
        ops = [x.op for x in seq]
        pat = [r"LD HL,\((\d+)\)", "EX DE,HL", r"LD HL,\((\d+)\)", "LD B,H", "ADD HL,DE",
               r"LD \((\d+)\),HL", "EX DE,HL", r"LD HL,\((\d+)\)", "BIT 7,B", r"JR Z,(\d+)",
               "EX DE,HL", "CALL 25008", "LD A,L", "RRA", r"JR C,(\d+)", r"LD HL,\((\d+)\)",
               "JP \\(HL\\)"]
        if len(ops) < 17:
            return None
        g = []
        for o, p in zip(ops, pat):
            m = re.fullmatch(p, o)
            if not m:
                return None
            g += [int(x) for x in m.groups()]
        var, step, var2, limit, skip, exit_, addr = g
        if not (var == var2 and step == limit + 2 and addr == limit + 4
                and skip == seq[10].end and exit_ == seq[16].end):
            return None
        return Stmt(seq[0].addr, seq[16].end, "next", var=var, slot=limit, events=[],
                    text=f"NEXT {var_name(var)}")

    def match_wait(self, i):
        """LD HL,n : HALT : DEC HL : LD A,H : OR L : JR NZ,(the HALT)."""
        seq = self.instrs[i:i + 6]
        ops = [x.op for x in seq]
        if len(ops) < 6 or not re.fullmatch(r"LD HL,\d+", ops[0]):
            return None
        if ops[1:5] != ["HALT", "DEC HL", "LD A,H", "OR L"] or ops[5] != f"JR NZ,{seq[1].addr}":
            return None
        n = int(ops[0].split(",")[1])
        return Stmt(seq[0].addr, seq[5].end, "wait", text=f"WAIT {n}  [HALT x {n}]")

    # ------------------------------------------------------------ symbolic execution

    def step(self, st, ins, ev):
        """Execute one instruction on the symbolic state. Appends any side
        effect to ev. Raises Fail when the model can't follow."""
        op = ins.op
        R = st.r
        m = re.fullmatch(r"LD (HL|DE|BC),(\d+)", op)
        if m:
            R[m.group(1)] = ("n", int(m.group(2)))
            return
        m = re.fullmatch(r"LD HL,\((\d+)\)", op)
        if m:
            R["HL"] = ("v", int(m.group(1)))
            return
        m = re.fullmatch(r"LD \((\d+)\),HL", op)
        if m:
            ev.append(("let", ("n", int(m.group(1))), st.get("HL")))
            return
        if op == "EX DE,HL":
            R["HL"], R["DE"] = R["DE"], R["HL"]
            return
        m = re.fullmatch(r"PUSH (HL|DE|BC)", op)
        if m:
            # A spill of a register holding nothing still balances its POP.
            v = R[m.group(1)]
            st.stack.append(("junk",) if v is UNKNOWN else v)
            return
        m = re.fullmatch(r"POP (HL|DE|BC)", op)
        if m:
            if not st.stack:
                raise Fail("POP of an empty stack")
            v = st.stack.pop()
            R[m.group(1)] = UNKNOWN if v == ("junk",) else v
            return
        m = re.fullmatch(r"ADD HL,(DE|BC|HL)", op)
        if m:
            a = st.get("HL")
            b = st.get(m.group(1))
            if m.group(1) == "HL":
                R["HL"] = ("bin", "*", a, ("n", 2))
            else:
                R["HL"] = ("bin", "+", a, b)
            st.carry = UNKNOWN
            return
        if op == "INC HL":
            a = st.get("HL")
            R["HL"] = ("bin", "+", a, ("n", 1))
            return
        if op == "DEC HL":
            R["HL"] = ("bin", "-", st.get("HL"), ("n", 1))
            return
        if op == "XOR A":
            R["A"] = ("c8", 0)
            st.carry = 0
            st.flags = UNKNOWN
            return
        if op == "SBC HL,DE":
            if st.carry != 0:
                raise Fail("SBC with the carry unknown")
            R["HL"] = ("bin", "-", st.get("HL"), st.get("DE"))
            st.flags = UNKNOWN
            st.carry = UNKNOWN
            return
        if op == "LD A,H":
            R["A"] = ("hi", st.get("HL"))
            return
        if op == "LD A,L":
            R["A"] = ("lo", st.get("HL"))
            return
        m = re.fullmatch(r"LD A,(\d+)", op)
        if m:
            R["A"] = ("c8", int(m.group(1)))
            return
        if op == "OR L":
            a = st.get("A")
            hl = st.get("HL")
            if a != ("hi", hl):
                raise Fail("OR L without A = H")
            st.flags = ("nz", hl)
            st.carry = 0
            R["A"] = UNKNOWN
            return
        m = re.fullmatch(r"(JP|JR) (N?Z),(\d+)", op)
        if m:
            if st.flags is UNKNOWN:
                raise Fail("conditional jump on unknown flags")
            ev.append(("if", m.group(2), st.flags[1], int(m.group(3))))
            return
        m = re.fullmatch(r"JP (\d+)", op)
        if m:
            ev.append(("goto", int(m.group(1))))
            return
        if op == "RET":
            ev.append(("return",))
            return
        if op == "RES 7,H":
            R["HL"] = ("bin", "AND", st.get("HL"), ("n", 32767))
            return
        if op == "LDW HL,(HL)":
            R["HL"] = ("dpeek", st.get("HL"))
            R["A"] = UNKNOWN
            return
        if op == "STW (HL),DE":
            ev.append(("let", st.get("HL"), st.get("DE")))
            R["HL"] = ("bin", "+", R["HL"], ("n", 1))
            return
        if op in ("LD (HL),E", "LD (HL),A"):
            v = ("lo", st.get("DE")) if op.endswith("E") else st.get("A")
            ev.append(("poke", st.get("HL"), v))
            return
        if op == "LD BC,HL":
            R["BC"] = st.get("HL")
            return
        if op == "HALT":
            ev.append(("halt",))
            return
        if op.startswith("CALC "):
            codes = [int(x) for x in op[5:].split(",")]
            if codes[-1] != 0x38:
                raise Fail("calculator without end-calc")
            for c in codes[:-1]:
                if c not in CALC_OPS or len(st.fp) < 2:
                    raise Fail(f"calculator literal {c}")
                b = st.fp.pop()
                a = st.fp.pop()
                st.fp.append(("fp", CALC_OPS[c], a, b))
            R["A"] = R["BC"] = R["DE"] = R["HL"] = UNKNOWN
            return
        if op == "RST 16":
            ev.append(("out", st.get("A")))
            R["A"] = UNKNOWN
            return
        m = re.fullmatch(r"CALL (\d+)", op)
        if m:
            self.call(st, ins, int(m.group(1)), ev)
            return
        raise Fail(f"instruction not modelled: {op}")

    def clobber(self, st, regs):
        for r in regs.split():
            st.r[r] = UNKNOWN
        st.r["A"] = UNKNOWN
        st.flags = UNKNOWN
        st.carry = UNKNOWN

    def call(self, st, ins, n, ev):
        R = st.r
        if n in BINOPS:
            op, clob = BINOPS[n]
            a, b = st.get("HL"), st.get("DE")
            if n == 24911:
                R["HL"] = ("bin", "/", a, b)
                self.clobber(st, clob)
                R["DE"] = ("mod", a, b)
                return
            R["HL"] = ("bin", op, a, b)
            self.clobber(st, clob)
            return
        if n in BINFNS:
            name, clob = BINFNS[n]
            R["HL"] = ("fn", name, st.get("HL"), st.get("DE"))
            self.clobber(st, clob)
            return
        if n in UNOPS:
            name, clob = UNOPS[n]
            v = ("un", name, st.get("HL"))
            if name == "CODE":
                v = st.get("HL")
            if name in SIDE_EFFECT_FNS:
                v = fx(v)
                self.fx_pending[v[1]] = (v, ins.addr)
            R["HL"] = v
            self.clobber(st, clob)
            return
        if n == 25026:
            v = fx(("inkey",))
            self.fx_pending[v[1]] = (v, ins.addr)
            self.clobber(st, "DE BC HL")
            R["HL"] = v
            return
        if n == 5633:
            ev.append(("chan", st.get("A")))
        elif n == 8252:
            ev.append(("str", st.get("DE"), st.get("BC")))
        elif n == 25252:
            ev.append(("num", st.get("HL")))
        elif n == 7997:
            ev.append(("pause", st.get("BC")))
        elif n == 8855:
            ev.append(("border", st.get("A")))
        elif n == 949:
            ev.append(("beeper", st.get("DE"), st.get("HL")))
        elif n == 11563:
            st.fp.append(("fp", "n", st.get("BC")))
        elif n == 25416:
            if len(st.fp) != 1:
                raise Fail("BEEP without its duration on the calculator stack")
            ev.append(("beep", st.fp.pop(), st.get("HL")))
        elif n == 25431:
            ev.append(("sprite", st.get("HL")))
        elif n == 25310:
            v = fx(("un", "INPUT", ("n", 0)))
            self.clobber(st, "DE BC HL")
            R["HL"] = v
            self.fx_pending[v[1]] = (v, ins.addr)
            return
        elif n in ROM_STMTS:
            ev.append((ROM_STMTS[n].lower(),))
        elif CODE_START <= n < CODE_END:
            ev.append(("gosub", n))
        else:
            raise Fail(f"call to {n} not modelled")
        self.clobber(st, "DE BC HL")

    # ------------------------------------------------------------ the sweep

    def run(self):
        st = State()
        i = 0
        start = 0        # index of the current statement's first instruction
        ev = []
        instrs = self.instrs

        def close(end_i, events):
            a = instrs[start].addr
            e = instrs[end_i].end
            self.stmts.append(Stmt(a, e, "ev", events=events))

        def raw_from(s, e):
            for ins in instrs[s:e + 1]:
                self.stmts.append(Stmt(ins.addr, ins.end, "raw", ins=ins))

        def dropped(st):
            """Close a statement for side-effecting values no longer held."""
            live = st.live()
            gone = [k for k in self.fx_pending if k not in live]
            evs = []
            for k in gone:
                tree, _ = self.fx_pending.pop(k)
                evs.append(("call", tree))
            return evs

        while i < len(instrs):
            ins = instrs[i]
            if ins.addr in self.labels and i != start:
                # A jump lands mid-statement: what came before can't be printed.
                raw_from(start, i - 1)
                self.stmts[-1].why = "a jump lands in the middle of this statement"
                st.reset()
                start = i
                ev = []
            if ins.addr in self.labels:
                st.reset()
                self.fx_pending.clear()
            if i == start:
                for tm in (self.match_next, self.match_wait):
                    s = tm(i)
                    if s:
                        self.stmts.append(s)
                        i = self.index[s.end] if s.end in self.index else len(instrs)
                        start = i
                        st.reset()
                        break
                else:
                    s = None
                if s:
                    continue
            # A fresh load of HL discards a side-effecting value nobody kept.
            if re.fullmatch(r"LD HL,\(?\d+\)?", ins.op) and self.fx_pending:
                saved = st.r["HL"]
                st.r["HL"] = None
                evs = dropped(st)
                st.r["HL"] = saved
                if evs and not st.stack:
                    if i > start:
                        close(i - 1, ev + evs)
                    start = i
                    ev = []
            try:
                before = len(ev)
                self.step(st, ins, ev)
            except Fail as exc:
                raw_from(start, i)
                self.stmts[-1].why = str(exc)
                st.reset()
                self.fx_pending.clear()
                i += 1
                start = i
                ev = []
                continue
            for e in ev[before:]:
                for k in fx_ids(e):
                    self.fx_pending.pop(k, None)
            if ev and not st.stack:
                nxt = instrs[i + 1] if i + 1 < len(instrs) else None
                last = ev[-1]
                if nxt is None or nxt.addr in self.labels or not reads_state(nxt):
                    done = True
                elif len(ev) > before:
                    # just made an effect: the statement ends unless it goes on
                    # storing into the same sprite block
                    done = not continues_block(st, last, nxt)
                else:
                    done = False
                if done:
                    close(i, ev)
                    ev = []
                    start = i + 1
                    if ev_resets(last):
                        st.reset()
                        self.fx_pending.clear()
            i += 1
        if start < len(instrs):
            raw_from(start, len(instrs) - 1)


def continues_block(st, last, nxt):
    """A sprite block's fields are stored one after another by one statement,
    the address carried in HL: after a store into a block, an INC HL or PUSH
    HL goes on with the same statement."""
    if last[0] not in ("let", "poke") or nxt.op not in ("INC HL", "PUSH HL"):
        return False
    hl = st.r["HL"]
    return hl is not None and in_block(simplify(hl)) is not None


def in_block(a):
    """(block, offset) for an address within a sprite block, else None."""
    off = 0
    while True:
        if a[0] == "blockaddr":
            return a, off
        if const(a) and SPRITE_TABLE <= a[1] < SPRITE_TABLE + 8 * 32:
            return ("blockaddr", ("n", (a[1] - SPRITE_TABLE) // 8)), off + (a[1] - SPRITE_TABLE) % 8
        if a[0] == "bin" and a[1] == "+" and const(a[3]):
            off += a[3][1]
            a = a[2]
        else:
            return None


def reads_state(ins):
    """Whether an instruction reads a register left by the one before. A
    statement still being gathered ends before one that doesn't."""
    op = ins.op
    if re.fullmatch(r"LD (HL|DE|BC|A),\d+|LD HL,\(\d+\)|JP \d+|RET|HALT", op):
        return False
    m = re.fullmatch(r"CALL (\d+)", op)
    if m:
        n = int(m.group(1))
        return not (n in (3435, 3405, 7341, 25026, 25310) or CODE_START <= n < CODE_END)
    return True


def ev_resets(e):
    return e[0] in ("goto", "return", "gosub")


# ---------------------------------------------------------------- statements

def string_at(mem, addr, n):
    out = []
    buf = ""
    for b in mem[addr:addr + n]:
        if 32 <= b < 127 and b != 34:
            buf += chr(b)
        elif b == 34:
            buf += '""'
        else:
            if buf:
                out.append(f'"{buf}"')
                buf = ""
            out.append(f"CHR$ {b}")
    if buf:
        out.append(f'"{buf}"')
    return "+".join(out) if out else '""'


def render_print(mem, items):
    """items: the events of a PRINT, in order. Returns the PRINT's text."""
    parts = []
    q = list(items)
    text = []

    def flush_text():
        if text:
            parts.append('"' + "".join(text) + '"')
            text.clear()

    k = 0
    while k < len(q):
        e = q[k]
        if e[0] == "out":
            v = e[1]
            if v[0] == "c8" and v[1] in PRINT_CTRL:
                flush_text()
                if k + 1 < len(q) and q[k + 1][0] == "out":
                    parts.append(f"{PRINT_CTRL[v[1]]} {render(q[k + 1][1])}")
                    k += 2
                    continue
            if v[0] == "c8" and v[1] in (22, 23):
                flush_text()
                if k + 2 < len(q) and q[k + 1][0] == "out" and q[k + 2][0] == "out":
                    word = "AT" if v[1] == 22 else "TAB"
                    parts.append(f"{word} {render(q[k + 1][1])},{render(q[k + 2][1])}")
                    k += 3
                    continue
            if v[0] == "c8" and 32 <= v[1] < 127:
                text.append(chr(v[1]))
            elif v[0] == "c8" and v[1] == 13:
                flush_text()
                parts.append("'")
            elif v[0] == "c8" and v[1] == 6:
                flush_text()
                parts.append(",")
            elif v[0] == "c8":
                flush_text()
                parts.append(f"CHR$ {v[1]}")
            else:
                flush_text()
                parts.append(f"CHR$ {render(v, 11)}")
        elif e[0] == "str":
            flush_text()
            d, n = e[1], e[2]
            if const(d) and const(n):
                parts.append(f"{string_at(mem, d[1], n[1])}")
            else:
                parts.append(f"STR({render(d)},{render(n)})")
        elif e[0] == "num":
            flush_text()
            parts.append(render(e[1]))
        k += 1
    flush_text()
    # Join: items separated by ';' except around the apostrophe and comma.
    s = ""
    for p in parts:
        if p in ("'", ","):
            s = s.rstrip("; ") + p
        else:
            s += p + "; "
    s = s.rstrip()
    return s


def describe(mem, ev):
    """The text of a statement from its events, or None to print it raw."""
    k = ev[0]
    if k == "let":
        dst = target(ev[1])
        val = ev[2]
        if dst is None:
            return f"DPOKE {render(ev[1])}, {render(val)}"
        if simplify(ev[1]) == ("n", 23563):
            return f"RANDOMIZE  [RND's seed, 23563 = {render(val)}]"
        if const(simplify(ev[1])) and simplify(ev[1])[1] < VAR_START:
            return f"DPOKE {addr_name(simplify(ev[1])[1])}, {render(val)}"
        return f"LET {dst} = {render(val)}"
    if k == "poke":
        a = simplify(ev[1])
        return f"POKE {addr_name(a[1]) if const(a) else render(a)}, {render(ev[2])}"
    if k == "if":
        cond, e, t = ev[1], ev[2], ev[3]
        if cond == "Z":
            return f"IF {render(e)} THEN", t
        return f"IF {render(e)} THEN GOTO {t}"
    if k == "goto":
        return f"GOTO {ev[1]}"
    if k == "gosub":
        return f"GOSUB {sub_name(ev[1])}"
    if k == "return":
        return "RETURN"
    if k == "cls":
        return "CLS"
    if k == "pause":
        return f"PAUSE {render(ev[1])}"
    if k == "border":
        return f"BORDER {render(ev[1])}"
    if k == "beeper":
        return f"BEEPER {render(ev[1])}, {render(ev[2])}  [ROM 949: DE cycles, HL period]"
    if k == "beep":
        return f"BEEP {render(ev[1])}, {render(ev[2])}"
    if k == "halt":
        return "HALT"
    if k == "call":
        return f"CALL {render(ev[1])}  [result unused]"
    return None


def sub_name(a):
    n = names.SUBS.get(a)
    return f"{a} [{n}]" if n else str(a)


# The 8-byte parameter block 25431 reads: see compiler.md.
SPRITE_FIELDS = {0: "gfx", 1: "gfx_hi", 2: "x", 3: "y", 4: "rows", 5: "width", 6: "mode", 7: "colour"}


def describe_sprite(evs):
    """Stores into one sprite block, perhaps followed by CALL 25431: the
    compiler's sprite statement. None if the events aren't that."""
    put = evs[-1][0] == "sprite"
    stores = evs[:-1] if put else evs
    block = None
    if put:
        b = in_block(simplify(evs[-1][1]))
        if b is None or b[1] != 0:
            return None
        block = b[0]
    fields = []
    for e in stores:
        if e[0] not in ("poke", "let"):
            return None
        b = in_block(simplify(e[1]))
        if b is None or (block is not None and b[0] != block):
            return None
        block, off = b
        name = SPRITE_FIELDS.get(off, f"+{off}")
        if e[0] == "let" and off != 0:
            name = f"word+{off}"
        v = e[2]
        if v[0] == "lo":
            v = v[1]
        fields.append(f"{name}={render(v)}")
    if block is None:
        return None
    n = render(block[1])
    word = "SPRITE" if put else "SPRITE SET"
    return f"{word} {n}" + (" " + ", ".join(fields) if fields else "")


def build(dec):
    """From raw statements to printable ones: PRINTs and FORs merged."""
    mem = dec.mem
    out = []
    pend = []    # the events of a PRINT being gathered: (stmt, events)

    def flush_print():
        if not pend:
            return
        evs = [e for _, es in pend for e in es]
        a, b = pend[0][0].addr, pend[-1][0].end
        kinds = {e[0] for e in evs}
        if kinds <= {"out", "perm"} and evs[-1][0] == "perm":
            # INK 7 as a statement: the codes printed, then made permanent
            text = render_print(mem, [e for e in evs if e[0] == "out"]).rstrip(";")
        else:
            stream = None
            body = []
            for e in evs:
                if e[0] == "chan":
                    stream = render(e[1])
                elif e[0] in ("out", "str", "num"):
                    body.append(e)
            text = render_print(mem, body)
            ended = evs[-1][0] == "temps"
            lead = "PRINT" if stream in (None, "2") else f"PRINT #{stream};"
            if not ended:
                text += ";"
            elif text.endswith("'"):
                text = text[:-1]
            text = f"{lead} {text}".rstrip()
        out.append(Stmt(a, b, "print", text=text))
        pend.clear()

    for s in dec.stmts:
        if s.kind != "ev":
            flush_print()
            out.append(s)
            continue
        evs = s.events
        kinds = [e[0] for e in evs]
        if kinds == ["cls"] and len(pend) == 1 and [e[0] for e in pend[0][1]] == ["chan"]:
            # CLS opens stream 2 first
            a = pend[0][0].addr
            pend.clear()
            out.append(Stmt(a, s.end, "cls", text="CLS", events=evs))
            continue
        if all(k in ("out", "str", "num", "chan", "temps", "perm") for k in kinds):
            if kinds[0] == "chan" and pend:
                flush_print()
            pend.append((s, evs))
            if kinds[-1] in ("temps", "perm"):
                flush_print()
            continue
        flush_print()
        if kinds[-1] == "sprite" or (kinds[0] in ("let", "poke") and in_block(simplify(evs[0][1]))):
            t = describe_sprite(evs)
            if t:
                out.append(Stmt(s.addr, s.end, "sprite", text=t, events=evs))
                continue
        if len(evs) > 1 and all(k == "call" for k in kinds[:-1]):
            # side-effecting values dropped before the statement's own effect
            for e in evs[:-1]:
                out.append(Stmt(s.addr, s.addr, "ev", text=describe(mem, e)))
            evs = evs[-1:]
        if len(evs) != 1:
            out.append(Stmt(s.addr, s.end, "raw", why="several effects in one statement: "
                            + " ".join(kinds), ins=None, sub=dec.instrs[dec.index[s.addr]:dec.index.get(s.end, len(dec.instrs))]))
            continue
        d = describe(mem, evs[0])
        if d is None:
            out.append(Stmt(s.addr, s.end, "raw", why=f"no description for {kinds[0]}", ins=None,
                            sub=dec.instrs[dec.index[s.addr]:dec.index.get(s.end, len(dec.instrs))]))
            continue
        if isinstance(d, tuple):
            out.append(Stmt(s.addr, s.end, "if", text=d[0], else_=d[1], events=evs))
        else:
            kind = "ifgoto" if evs[0][0] == "if" else evs[0][0]
            out.append(Stmt(s.addr, s.end, kind, text=d, ev=evs[0], events=evs))
    flush_print()
    return merge_for(out)


FOR_CLASHES = set()


def merge_for(stmts):
    """LET v = a : LET [s] = b : LET [s+2] = c : LET [s+4] = <next address>
    becomes FOR v = a TO b STEP c."""
    out = []
    i = 0
    while i < len(stmts):
        w = stmts[i:i + 4]
        if len(w) == 4 and all(getattr(x, "ev", (None,))[0] == "let" for x in w):
            dsts = [simplify(x.ev[1]) for x in w]
            vals = [x.ev[2] for x in w]
            if (all(const(d) for d in dsts) and FOR_SLOTS[0] <= dsts[1][1] < FOR_SLOTS[1]
                    and dsts[2][1] == dsts[1][1] + 2 and dsts[3][1] == dsts[1][1] + 4
                    and vals[3] == ("n", w[3].end)):
                letter = for_letter(dsts[1][1])
                if FOR_LETTERS.setdefault(dsts[0][1], letter) != letter:
                    FOR_CLASHES.add(dsts[0][1])
                var = var_name(dsts[0][1])
                step = render(vals[2])
                text = f"FOR {var} = {render(vals[0])} TO {render(vals[1])}"
                if step != "1":
                    text += f" STEP {step}"
                text += f"  [slot {letter}: {dsts[1][1]}]"
                out.append(Stmt(w[0].addr, w[3].end, "for", text=text, var=dsts[0][1], slot=dsts[1][1],
                                events=[x.ev for x in w]))
                i += 4
                continue
        out.append(stmts[i])
        i += 1
    return out


# ---------------------------------------------------------------- verification
# Each statement whose effect is a store or a branch is run on the Z80 (the
# original's own code, in SkoolKit's simulator) from random variable values,
# and its effect compared with the expression tree evaluated in Python under
# the runtime library's semantics. The Python side is the port's model of the
# library, so a pass checks both the decompiler and that model.

def u16(v):
    return v & 0xFFFF


def mag(v):
    """|v| as the library takes it: 32768 stays 32768."""
    return u16(-v) if v & 0x8000 else v


def lib_mul(a, b):
    """HL * DE as 24880 computes it: shift-and-add on the magnitudes, the
    product negated if exactly one operand was negative. It is the true
    product (mod 65536) only while no partial sum passes 65535: the carry out
    of ADD HL,DE is rotated into DE by the RL E that follows, and DE's top
    bit comes back into BC by the next RR B."""
    bc, de, hl, carry = mag(a), mag(b), 0, 0
    for _ in range(16):
        b_, c_ = bc >> 8, bc & 255
        b_, carry = (carry << 7) | (b_ >> 1), b_ & 1        # RR B
        c_, carry = (carry << 7) | (c_ >> 1), c_ & 1        # RR C
        bc = b_ << 8 | c_
        if carry:                                          # ADD HL,DE
            hl += de
            carry, hl = hl >> 16, hl & 0xFFFF
        e_, d_ = de & 255, de >> 8
        e_, carry = ((e_ << 1) | carry) & 255, e_ >> 7     # RL E
        d_, carry = ((d_ << 1) | carry) & 255, d_ >> 7     # RL D
        de = d_ << 8 | e_
    return u16(-hl) if (a ^ b) & 0x8000 else hl


def lib_div(a, b):
    """(quotient, remainder) as 24911 leaves them in HL and DE: magnitudes
    divided, the quotient negated if exactly one operand was negative, the
    remainder never negated. Dividing by 0 gives (0, 0)."""
    ma, mb = mag(a), mag(b)
    if mb == 0:
        return 0, 0
    q, r = ma // mb, ma % mb
    q &= 0xFFFF
    return (u16(-q) if (a ^ b) & 0x8000 else q), r


def lib_rnd(mem, n):
    """RND n (25214): advance the seed at 23563 (the ROM's DEFADD), return
    seed MOD n."""
    seed = mem[23563] | mem[23564] << 8
    h = lib_mul(u16(seed + 1), 77)
    if h == 0:
        h = 78
    h = u16(h - 1)
    mem[23563], mem[23564] = h & 255, h >> 8
    return lib_div(h, n)[1]


class Skip(Exception):
    pass


def evaluate(e, mem):
    k = e[0]
    if k == "n":
        return e[1] & 0xFFFF
    if k == "v":
        return mem[e[1]] | mem[e[1] + 1] << 8
    if k == "fx":
        if e[2][0] == "un" and e[2][1] == "RND":
            return lib_rnd(mem, evaluate(e[2][2], mem))
        raise Skip("side effect")
    if k == "bin":
        a = evaluate(e[2], mem)
        b = evaluate(e[3], mem)
        op = e[1]
        sa, sb = s16(a), s16(b)
        return {
            "+": lambda: u16(a + b), "-": lambda: u16(a - b), "*": lambda: lib_mul(a, b),
            "/": lambda: lib_div(a, b)[0], "=": lambda: int(a == b), "<>": lambda: int(a != b),
            "<": lambda: int(sa < sb), ">": lambda: int(sa > sb), "<=": lambda: int(sa <= sb),
            ">=": lambda: int(sa >= sb), "AND": lambda: a & b, "OR": lambda: a | b,
        }[op]()
    if k == "mod":
        return lib_div(evaluate(e[1], mem), evaluate(e[2], mem))[1]
    if k == "un":
        a = evaluate(e[2], mem)
        op = e[1]
        if op == "NEG":
            return u16(-a)
        if op == "NOT":
            return int(a == 0)
        if op == "ABS":
            return mag(a)
        if op == "SGN":
            return 0 if a == 0 else (0xFFFF if a & 0x8000 else 1)
        if op == "PEEK":
            return mem[a]
        if op == "CODE":
            return a
        raise Skip(op)
    if k == "fn":
        a = evaluate(e[2], mem)
        b = evaluate(e[3], mem)
        if e[1] == "ATTR":
            lo = (((a & 7) << 5) ^ b) & 0xFF   # the library XORs the column in
            hi = ((a >> 3) & 3) ^ 0x58
            return mem[hi << 8 | lo]
        if e[1] == "POINT":
            x, y = a & 255, b & 255
            if y > 175:
                raise Skip("POINT off screen: a ROM error")
            y = 175 - y
            addr = 0x4000 | (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2 | x >> 3
            return (mem[addr] >> (7 - (x & 7))) & 1
        raise Skip(e[1])
    if k == "dpeek":
        a = evaluate(e[1], mem)
        return mem[a] | mem[u16(a + 1)] << 8
    if k == "lo":
        return evaluate(e[1], mem) & 255
    if k == "hi":
        return evaluate(e[1], mem) >> 8
    if k == "c8":
        return e[1]
    raise Skip(k)


def storable(a):
    """Whether a trial may let a store land at a: not in the code, the
    stack, the system variables or the interrupt vector table."""
    return (0x5B00 <= a < 24400 or FOR_SLOTS[0] <= a < SPRITE_TABLE + 8 * 32
            or CODE_END <= a < 0xFE00)


def expected(stmt, mem):
    """Apply the statement's effect to mem; return the next PC, or None for
    the fall-through."""
    for ev in stmt.events:
        if ev[0] == "let":
            a = evaluate(ev[1], mem)
            v = evaluate(ev[2], mem)
            if not storable(a) or not storable(u16(a + 1)):
                raise Skip("store outside the variables")
            mem[a], mem[u16(a + 1)] = v & 255, v >> 8
        elif ev[0] == "poke":
            a = evaluate(ev[1], mem)
            v = evaluate(ev[2], mem)
            if not storable(a):
                raise Skip("store outside the variables")
            mem[a] = v & 255
        elif ev[0] == "if":
            v = evaluate(ev[2], mem)
            taken = (v == 0) if ev[1] == "Z" else (v != 0)
            return ev[3] if taken else None
        else:
            raise Skip(ev[0])
    return None


def expected_next(stmt, mem):
    var, slot = stmt.var, stmt.slot
    rd = lambda a: mem[a] | mem[a + 1] << 8
    step, limit, back = rd(slot + 2), rd(slot), rd(slot + 4)
    v = u16(rd(var) + step)
    mem[var], mem[var + 1] = v & 255, v >> 8
    done = s16(limit) < s16(v) if not step & 0x8000 else s16(v) < s16(limit)
    return None if done else back


def verify(snap_path, stmts, trials, seed=1):
    import random

    from skoolkit import CSimulator
    from skoolkit.simutils import PC, SP, from_snapshot
    rng = random.Random(seed)
    snapshot = Snapshot.get(snap_path)
    sim = from_snapshot(CSimulator, snapshot)
    base = bytes(sim.memory)
    sp0 = sim.registers[SP]
    checked = failed = skipped = 0
    for st in stmts:
        if st.kind not in ("let", "poke", "if", "ifgoto", "for", "sprite", "next"):
            continue
        ok = True
        ran = 0
        for t in range(trials):
            mem = bytearray(base)
            # Small values make array indexes land in their arrays; some
            # trials use the full range.
            for a in range(VAR_START, VAR_START + 1024, 2):
                v = rng.randint(0, 24) if t % 2 == 0 else rng.randint(0, 65535)
                mem[a], mem[a + 1] = v & 255, v >> 8
            for a in range(FOR_SLOTS[0], FOR_SLOTS[1], 2):
                v = rng.randint(-3, 24) & 0xFFFF
                mem[a], mem[a + 1] = v & 255, v >> 8
            mem[23563], mem[23564] = rng.randint(0, 255), rng.randint(0, 255)
            want = bytearray(mem)
            try:
                if st.kind == "next":
                    back = rng.randint(CODE_START, CODE_END - 1)
                    want[st.slot + 4], want[st.slot + 5] = back & 255, back >> 8
                    mem[st.slot + 4], mem[st.slot + 5] = back & 255, back >> 8
                    goes = expected_next(st, want)
                elif st.kind == "sprite" and st.events[-1][0] == "sprite":
                    # check the block's stores, stopping at the CALL 25431
                    sub = Stmt(st.addr, st.end - 3, "sprite", events=st.events[:-1])
                    goes = expected(sub, want)
                else:
                    goes = expected(st, want)
            except Skip as exc:
                st.skip = str(exc)
                continue
            sim.memory[:] = mem
            sim.registers[PC] = st.addr
            sim.registers[SP] = sp0
            stops = {st.end}
            if st.kind == "sprite" and st.events[-1][0] == "sprite":
                stops = {st.end - 3}
                goes = st.end - 3
            if goes is not None:
                stops.add(goes)
            if st.kind in ("if", "ifgoto"):
                stops.add(st.events[0][3])
            if st.kind == "next":
                stops.add(back)
            for _ in range(200000):
                sim.run()
                if sim.registers[PC] in stops:
                    break
            got = bytes(sim.memory)
            pc = sim.registers[PC]
            want_pc = st.end if goes is None else goes
            # Compare RAM outside the stack and the ROM's workspace.
            diff = [a for a in range(0x5C00, 0x10000)
                    if got[a] != want[a] and not (sp0 - 64 <= a < sp0) and not (23552 <= a < 23734)]
            diff += [a for a in (23563, 23564) if got[a] != want[a]]
            ran += 1
            if pc != want_pc or diff:
                ok = False
                st.verify = f"VERIFY FAILED: pc {pc} want {want_pc}, differ at {diff[:6]}"
                break
        if ran == 0:
            skipped += 1
        elif ok:
            checked += 1
            st.verified = ran
        else:
            failed += 1
    return checked, failed, skipped


# ---------------------------------------------------------------- output

def raw_text(ins):
    return f"Z80: {ins.op:<16} ; " + " ".join(f"{b:02x}" for b in ins.data)


def write_listing(dec, stmts, path, stats, executed=None):
    labels = dec.labels
    # Indentation: FOR bodies (to the NEXT with the same slots) and IF bodies
    # (to the else address).
    spans = []
    nexts = {}
    for s in stmts:
        if s.kind == "next":
            nexts.setdefault(s.slot, []).append(s)
    for s in stmts:
        if s.kind == "for":
            for n in nexts.get(s.slot, []):
                if n.addr >= s.end:
                    spans.append((s.end, n.addr))
                    break
        if s.kind == "if" and s.else_ > s.end:
            spans.append((s.end, s.else_))
    def mark(a, b):
        if not executed or any(x in executed for x in range(a, b)):
            return " "
        return "~"

    lines = []
    lines.append("' Cauldron (Palace Software, 1985): the compiled BASIC, decompiled by")
    lines.append("' tools/decompile.py from build/cauldron.z80. Each line starts with the")
    lines.append("' address of its first instruction. Indentation shows FOR bodies and IF")
    lines.append("' bodies (an IF's [else N] is where a false condition goes). AND, OR and")
    lines.append("' NOT are 16-bit: AND/OR bitwise, NOT x = (x = 0). @a(i) is an element's")
    lines.append("' address. Raw Z80: lines are code the tool could not match.")
    lines.append("' Constants print unsigned (except -256..-1). SPRITE n: the block at")
    lines.append("' 24759 + 8*n and a CALL 25431; SPRITE SET n only fills the block.")
    if executed:
        lines.append("' A '~' after the address: no execution map given ran that statement.")
    lines.append("'")
    for k, v in stats.items():
        lines.append(f"' {k}: {v}")
    lines.append("")
    for s in stmts:
        d = sum(1 for a, b in spans if a <= s.addr < b)
        ind = "  " * d
        srcs = labels.get(s.addr, [])
        gos = sorted({a for a, k in srcs if k == "GOSUB"})
        if gos:
            nm = names.SUBS.get(s.addr)
            lines.append("")
            lines.append(f"' ==== SUB {s.addr}{' ' + nm if nm else ''}  (GOSUB from "
                         + ", ".join(str(a) for a in gos) + ")")
        others = sorted({(a, k) for a, k in srcs if k in ("GOTO",)})
        if others:
            lines.append("'      <- GOTO from " + ", ".join(str(a) for a, _ in others))
        if s.kind == "raw":
            subs = [s.ins] if s.ins is not None else s.sub
            why = getattr(s, "why", None)
            for ins in subs:
                lines.append(f"{ins.addr:5d}{mark(ins.addr, ins.end)} {ind}{raw_text(ins)}")
            if why:
                lines[-1] += f"   <- {why}"
            continue
        if s.kind == "if":
            text = s.text + f"  [else {s.else_}]"
        else:
            text = s.text
        if getattr(s, "verify", None):
            text += f"   <- {s.verify}"
        lines.append(f"{s.addr:5d}{mark(s.addr, max(s.end, s.addr + 1))} {ind}{text}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def read_maps(maps):
    """The addresses in tools/zx.py --map files ($XXXX lines)."""
    executed = set()
    for p in maps:
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line:
                    executed.add(int(line[1:], 16) if line.startswith("$") else int(line))
    return executed


def coverage(dec, stmts, maps):
    """The figures the listing's header and the tool report."""
    matched = sum(s.nbytes for s in stmts if s.kind != "raw")
    rawb = rawlines = 0
    raw_addrs = set()
    for s in stmts:
        if s.kind == "raw":
            for ins in ([s.ins] if s.ins is not None else s.sub):
                rawb += ins.len
                rawlines += 1
                raw_addrs.update(range(ins.addr, ins.end))
    total = CODE_END - CODE_START
    stats = {
        "compiled region": f"{CODE_START}-{CODE_END - 1} ({total} bytes)",
        "bytes decompiled": f"{matched} ({100 * matched / total:.2f}%)",
        "bytes raw": f"{rawb} in {rawlines} raw lines",
        "statements": str(sum(1 for s in stmts if s.kind != "raw")),
    }
    if matched + rawb != total:
        stats["CHECK FAILED"] = f"decompiled + raw = {matched + rawb}, not {total}"
    if not maps:
        return stats
    instrs = disassemble(dec.mem, CODE_START, CODE_END)
    starts = {ins.addr: ins for ins in instrs}
    executed = {a for a in read_maps(maps) if CODE_START <= a < CODE_END}
    misaligned = sorted(a for a in executed if a not in starts)
    if misaligned:
        stats["CHECK FAILED"] = ("executed addresses that are not instruction starts: "
                                 + ", ".join(map(str, misaligned[:10])))
    exb = sum(starts[a].len for a in executed if a in starts)
    ex_raw = sorted(a for a in executed if a in raw_addrs)
    stats["executed (maps)"] = (f"{len(executed)} of {len(instrs)} instructions, {exb} of {total} bytes"
                                f" ({100 * exb / total:.1f}%)")
    stats["executed bytes in raw lines"] = str(sum(starts[a].len for a in ex_raw)) + (
        "" if not ex_raw else " (" + ", ".join(str(a) for a in ex_raw[:20]) + ")")
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snap", default="build/cauldron.z80")
    ap.add_argument("--out", default="build/cauldron.bas")
    ap.add_argument("--map", action="append", default=[], help="execution map(s) from tools/zx.py --map")
    ap.add_argument("--verify", type=int, default=4, metavar="N",
                    help="run each store or branch statement on the Z80 N times against its tree (0: don't)")
    args = ap.parse_args()
    mem = load_memory(args.snap)
    dec = Decompiler(mem)
    dec.run()
    find_arrays(dec.stmts)
    build(dec)              # once to learn the FOR variables' letters
    stmts = build(dec)
    stats = coverage(dec, stmts, args.map)
    taken = list(names.VARS.values()) + list(names.ARRAYS.values()) + [
        v for k, v in FOR_LETTERS.items() if k not in names.VARS]
    dups = sorted({n for n in taken if taken.count(n) > 1})
    if dups:
        stats["CHECK FAILED"] = "names given twice: " + ", ".join(dups)
    if FOR_CLASHES:
        stats["CHECK FAILED"] = "FOR variables with two slots: " + ", ".join(map(str, sorted(FOR_CLASHES)))
    if args.verify:
        ok, bad, skip = verify(args.snap, stmts, args.verify)
        stats["verified on the Z80"] = (f"{ok} statements agree, {bad} disagree, {skip} not checkable"
                                        f" ({args.verify} random trials each)")
        if bad:
            stats["CHECK FAILED"] = f"{bad} statements disagree with the Z80"
    write_listing(dec, stmts, args.out, stats, read_maps(args.map))
    for k, v in stats.items():
        print(f"{k}: {v}")
    print("wrote", args.out)
    return 1 if "CHECK FAILED" in stats else 0


if __name__ == "__main__":
    sys.exit(main())
