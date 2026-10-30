# The BASIC compiler's code

Cauldron's game logic is integer BASIC, compiled. ZXDB credits Phipps
Associates' BASIC compiler. This file is how that compiler's output works:
the code it generates for each construct, the runtime library it calls,
where it keeps variables, and how its RND works. `tools/decompile.py` turns
the code back into BASIC (`make bas` writes `build/cauldron.bas`), and
[logic-outline.md](logic-outline.md) maps the program it recovers.

Every address here is the original's, in decimal as the program's own
constants are. [runtime.md](runtime.md) covers the same library from the
machine code's side, with the hand-written routines and their costs, and
[data.md](data.md) the memory map and the data formats.

## The layout

| Addresses | What |
|---|---|
| 24600 | `JP 25592`: the entry the loader calls |
| 24603-24758 | FOR-loop slots: 26 of 6 bytes, one per letter a-z |
| 24759-24822 | sprite parameter blocks: 8 of 8 bytes, for 25431 |
| 24823-25591 | the runtime library (some of it unused: see below) |
| 25592-41014 | the compiled program; its last instruction is `JP 25592` at 41012 |
| 41015-41573 | the variables, 16-bit words |
| 41575-41589 | the string literals PRINT uses |
| 41590 on | the game's data and hand-written machine code |

The machine stack sits below 24600. Interrupts stay
in IM 1, so the ROM keeps FRAMES running; the library's IM 2 set-up at
25563 is never called.

## How the code generator works

Every value is a signed 16-bit integer, built in HL. There is no
expression stack beyond the machine stack: the generator walks the
expression tree and keeps a binary operator's left operand in DE.

- **A leaf** is `LD HL,n` or `LD HL,(var)`.
- **A binary operator** with a leaf on the right moves the left operand to
  DE, loads the right, and swaps: `EX DE,HL : LD HL,right : EX DE,HL`,
  leaving left in HL and right in DE, then the operator. For example
  25726-25731, `PEEK p * 17`:
  `CALL 25048 : EX DE,HL : LD HL,17 : EX DE,HL : CALL 24880`.
- **When the right operand is itself an expression**, the left one waits in
  DE, and DE is spilled with `PUSH DE` just before the right side needs it,
  and restored with `POP DE` after. 26276-26294, `53532 + q * 48`:
  `LD HL,53532 : EX DE,HL : LD HL,(q) : PUSH DE : EX DE,HL : LD HL,48 : EX
  DE,HL : CALL 24880 : POP DE : EX DE,HL : ADD HL,DE`. The spill is emitted
  even when DE holds nothing (27498 starts an IF's condition with a
  `PUSH DE` of the previous statement's leftovers).
- **Inline operators**: `+` is `ADD HL,DE`; `-` is `XOR A : SBC HL,DE`
  (28589, `magic - 1`); `* 2` from an array index is `ADD HL,HL`.
- **Library operators** are a CALL, HL op DE to HL: `*` 24880, `/` 24911,
  `=` 24980, `<>` 24989, `>=` 24998, `<=` 24999, `<` 25008, `>` 25023, `AND`
  25173, `OR` 25180. Comparisons give 0 or 1. AND and OR are bitwise on 16
  bits; since comparisons give 0 or 1 they also serve as logical AND and OR.
- **Functions of one argument** take it in HL and return in HL: `PEEK`
  25048, `IN` 25051, `NOT` 25187 (1 if HL = 0, else 0), `ABS` 25063, `USR`
  25205, `RND` 25214, and unary minus 24972 (`LD HL,1 : CALL 24972` is how
  `-1` is written, 27384).
- **Functions of two arguments** push the first, evaluate the second, then
  `EX DE,HL : POP HL`: the first in HL, the second in DE. `ATTR (line,
  column)` 25089 (27436-27446 is `ATTR(21, 28)`), `POINT (x, y)` 25073
  (27498).
- **INKEY$** is `CALL 25026 : CALL 25212`: 25026 returns the key's code (0
  for none) and 25212 is CODE, which is just `RET`. 39907, `LET q = CODE
  INKEY$`.
- **Constants are not folded**: `0 + v41433 - 1` (31079) is computed at run
  time. A constant array index is folded (see the variables).

### Statements

| Statement | Code | Example |
|---|---|---|
| `LET v = e` | e; `LD (v),HL` | 25592 |
| `LET a(i) = e` | i; `LD DE,a : DEC HL : ADD HL,HL : ADD HL,DE : PUSH HL`; e; `EX DE,HL : POP HL : LD (HL),E : INC HL : LD (HL),D` | 25630 |
| `a(i)` in an expression | i; `DEC HL : ADD HL,HL : LD BC,a : ADD HL,BC : LD A,(HL) : INC HL : LD H,(HL) : LD L,A` | 25757 |
| `POKE a, e` | a; `PUSH HL`; e; `LD A,L : POP HL : LD (HL),A` | 25757 |
| `IF e THEN ...` | e; `LD A,H : OR L : JP Z,`next line | 27178 |
| `IF e THEN GOTO n` | e; `LD A,H : OR L : JP NZ,n` | 27201 |
| `GOTO n` / `GOSUB n` / `RETURN` | `JP n` / `CALL n` / `RET` | 26688 / 26041 / 27015 |
| `FOR` / `NEXT` | see below | 25606 / 25648 |
| `RANDOMIZE` | `LD HL,(23672) : RES 7,H : LD (23563),HL` | 25598 |
| `PRINT` | see below | 29361 |
| `INK n` (also PAPER, BRIGHT, FLASH) | n; `LD A,16 : RST 16 : LD A,L : RST 16 : CALL 7341` | 28384 |
| `CLS` | `LD A,2 : CALL 5633 : CALL 3435` | 26709 |
| `BORDER n` | n; `LD A,L : CALL 8855` | 30457 |
| `PAUSE n` | n; `LD B,H : LD C,L : CALL 7997` | 32742 |
| `BEEP d, p` | d on the ROM calculator (below); p; `CALL 25416` | 39950 |
| SPRITE (below) | stores into a block at 24759, `CALL 25431` | 27753 |

An array element's address uses DE as scratch when it is the target of a
store, because nothing is live then; read in an expression, it uses BC so
that a left operand waiting in DE survives (29956-29972).

**IF** has no ELSE: the false branch jumps past the rest of the line,
as Sinclair BASIC's IF does. The decompiled listing prints `IF e THEN
[else n]` and indents the statements up to n. `IF e THEN GOTO n` is compiled to a single `JP NZ`.

**PRINT** selects stream 2 with `LD A,2 : CALL 5633` (CHAN-OPEN), sends
each item through RST 16, and ends with `CALL 3405` (TEMPS, the ROM's reset
of the temporary colours). A PRINT without a trailing `;` sends a 13 first.

- `AT y,x` is `LD A,22 : RST 16`, then each coordinate evaluated and sent
  with `LD A,L : RST 16`. TAB is the same with 23.
- `INK e` and its fellows evaluate e, then `LD A,16 : RST 16 : LD A,L : RST
  16` (16 INK, 17 PAPER, 18 FLASH, 19 BRIGHT, 20 INVERSE, 21 OVER).
- A string literal is `LD DE,addr : LD BC,len : CALL 8252` (PR-STRING),
  with the text in the pool at 41575.
- `CHR$ e` is e then `LD A,L : RST 16`.
- A number is e then `CALL 25252`.

RST 16 keeps HL, DE and BC (the ROM's PRINT-A-2 swaps to the alternate
set), and the generator relies on that: `LD HL,(q) : LD A,16 : RST 16 : LD
A,L : RST 16` (29379).

The game draws text in its own font: subroutine 31415 points CHARS at
55874 first, so the literals print as other glyphs ("O" for the magic
display's `%`, 31445).

**INK as a statement** sends the same codes to the current stream and then
`CALL 7341`, the end of the ROM's colour commands that copies ATTR_T to
ATTR_P.

**BEEP** is the only floating-point statement. The duration goes on the ROM
calculator's stack: each constant is `LD HL,n : LD B,H : LD C,L : CALL
11563` (STACK-BC), and arithmetic is an inline `RST 40` with its literals.
39950 is `BEEP 1/10, 0`: stack 1, stack 10, `RST 40 : DEFB 5, 56`
(division, end-calc), then `LD HL,0 : CALL 25416`, which stacks the pitch
from HL and calls the ROM's BEEP at 1016.

**The other sound** is a direct call to the ROM's BEEPER at 949 with DE =
cycles and HL = the period, both from BASIC: 32221, `LD HL,1 : PUSH HL :
LD HL,(t) : POP DE : CALL 949`. The listing prints it as `BEEPER 1, t`.

**HALT** is a statement: 30938 is `HALT : HALT : RET`. A wait of n frames
is compiled as a loop: `LD HL,n : HALT : DEC HL : LD A,H : OR L : JR NZ`
back to the HALT (36477, 40188). The listing prints `WAIT n`.

### FOR and NEXT

Each FOR variable has a 6-byte slot at `24603 + 6*k` for its letter (a is
0): the limit, the step and the loop-back address. Sinclair BASIC only
allows single-letter FOR variables, so the slot names the variable, and
every FOR on a variable uses the same slot. The letters found: d, e, f, m,
q, r, s, t, w and x.

```
FOR x = 1 TO 6                    25606
  LD HL,1 : LD (41277),HL         the variable = start
  LD HL,6 : LD (24741),HL         the limit
  LD HL,1 : LD (24743),HL         the step
  LD HL,25630 : LD (24745),HL     the loop-back address: the next statement
NEXT x                            25648
  LD HL,(41277) : EX DE,HL : LD HL,(24743) : LD B,H : ADD HL,DE : LD (41277),HL
  EX DE,HL : LD HL,(24741) : BIT 7,B : JR Z,+1 : EX DE,HL
  CALL 25008 : LD A,L : RRA : JR C,exit       ; exit: the statement after JP (HL)
  LD HL,(24745) : JP (HL)
```

So a loop's body always runs at least once; NEXT adds the step and exits
when `limit < v` for a step of 0 or more, or `v < limit` for a negative one
(the sign is bit 7 of the step's high byte). The comparison is signed. A
NEXT can sit inside an IF (29613), and GOTO out of a loop is common
(26585).

### The sprite statement

The block for sprite n is at `24759 + 8*n`:

| Byte | Field | Used by 25431 |
|---|---|---|
| 0-1 | the graphic's address | read through IX, a byte per cell row |
| 2 | x, 0-255 | PIXEL-ADD's C |
| 3 | y, BASIC's (0 at the bottom; the sprite's top row) | PIXEL-ADD's B, decremented per row |
| 4 | rows | the height in pixel rows |
| 5 | width, in bytes | |
| 6 | mode: 0, 1 or 2 | how the attributes are treated |
| 7 | colour | an attribute byte |

The statement stores fields into the block, each as `PUSH HL : value : POP
DE : EX DE,HL : LD (HL),E : INC HL`, skipping a field with `INC HL`. The
form that draws pushes the block's address twice and ends `POP HL : POP HL
: CALL 25431` (27753, `SPRITE 1 x=x, y=hag_y, mode=hag_mode`). The form that
only fills the block stores the graphic as a word and doesn't call
(28220, `SPRITE SET 3 gfx=..., rows=16, width=2, colour=71`).

25431 draws by XOR. For each pixel row it finds the screen address with the
ROM's PIXEL-ADD (8874), XORs `width` bytes in, shifted to the pixel when x
is not a multiple of 8 (one more byte then), and, for each of the cells the
row touches, sets the attribute:

- mode 0: a cell whose attribute is ATTR_P (23693) gets `colour`;
- mode 1: a cell whose attribute is `colour` gets ATTR_P;
- mode 2: the ROM's PO-ATTR code from 3044 applies the temporary colours
  (ATTR_T, MASK_T, P_FLAG), as PRINT would.

Rows go down the screen (y decreases). The attribute work is repeated for
every pixel row.

## The runtime library

HL is the result throughout; "keeps" lists the registers a routine leaves
alone, which the generator relies on. The decompiler's model of each is in
`tools/decompile.py` (BINOPS, UNOPS, `lib_mul`, `lib_div`, `lib_rnd`), and
is checked against the Z80 on every run.

| Address | Routine | Contract |
|---|---|---|
| 24823 | DRAW (unused) | the ROM's DRAW-LINE (9402) for the signed offsets in HL and DE |
| 24860 | (unused) | sets every attribute to `(attr AND NOT C) OR B` |
| 24880 | multiply | HL * DE. Keeps nothing else (DE is shifted, BC used). |
| 24911 | divide | HL / DE to HL, the remainder to DE. Keeps nothing else. |
| 24972 | negate | -HL. Keeps DE, BC. |
| 24980 | `=` | HL = DE. Keeps DE. |
| 24989 | `<>` | Keeps DE. |
| 24998 | `>=` | swaps first: DE is lost |
| 24999 | `<=` | Keeps DE. |
| 25008 | `<` | HL < DE, signed (with the overflow flag). Keeps DE. |
| 25023 | `>` | swaps, then 25008: DE is lost |
| 25026 | INKEY$ | the ROM's KEY-SCAN, K-TEST, K-DECODE (654, 798, 819): the key's code, 0 for none |
| 25048 | PEEK | |
| 25051 | IN | the port in HL |
| 25057 | signs | makes HL and DE positive, A = how many were negative; for 24880 and 24911 |
| 25063 | ABS | also 25057's second half |
| 25073 | POINT | x = HL, y = DE (low bytes), through PIXEL-ADD: 0 or 1 |
| 25089 | ATTR | line = HL, column = DE: PEEK of `0x5800 + 256*((line >> 3) AND 3) + ((32*line AND 0xE0) XOR column)` |
| 25106 | SCREEN$ (unused) | compares the cell with the font at CHARS: the code, or 0 |
| 25173 | AND | bitwise |
| 25180 | OR | bitwise |
| 25187 | NOT | 1 if HL = 0, else 0 |
| 25195 | SGN (unused) | |
| 25205 | USR | `CALL 25211` (`JP (HL)`), then HL = BC |
| 25212 | CODE | a bare `RET`, called once, between INKEY$ and the store (39910): CODE, free since 25026 already gives a code |
| 25214 | RND | see below. Keeps DE. |
| 25252 | print a number | signed decimal through RST 16, no leading zeros; powers of ten at 25244 |
| 25310 | INPUT (unused) | a number from the editor |
| 25380 | (unused) | prints `[`line`]` (PPC) in the lower screen, then a BREAK check: a compiler debug aid |
| 25416 | BEEP | stacks HL (the pitch) on the calculator, then the ROM's BEEP (1016) |
| 25431 | sprite | HL = the block's address: see above |
| 25563 | (unused) | IM 2 with the vector at 65279 pointing to 25576 |
| 25576 | (unused) | the IM 2 handler: `CALL 0` (patched) between saved registers, then the ROM's at 58 |

### Multiply and divide: the exact arithmetic

The port must reproduce these, since RND depends on the multiply.

**Divide** (24911) takes the magnitudes (32768 stays 32768), divides
unsigned, and negates the quotient if exactly one operand was negative. The
remainder in DE is never negated. Dividing by 0 returns 0 with DE = 0, no
error.

**Multiply** (24880) is shift-and-add on the magnitudes, the product
negated if exactly one operand was negative. It is not the true product
mod 65536 when a partial sum overflows: the carry out of `ADD HL,DE` is
rotated into DE by the `RL E` that follows, and DE's top bit returns into BC
through the next `RR B`. As Python (the model `tools/decompile.py` checks
against the Z80):

```python
def mag(v):                       # |v| as 16 bits; 32768 stays 32768
    return (-v) & 0xFFFF if v & 0x8000 else v

def lib_mul(a, b):
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
    return (-hl) & 0xFFFF if (a ^ b) & 0x8000 else hl
```

RND's multiply overflows all the time. Whether any of the game's own
multiplications can overflow in play hasn't been checked; the port should
use this model for all of them.

## RND

The seed is the word at 23563, the ROM's DEFADD system variable (only used
while a DEF FN runs, so free here); the ROM's own SEED (23670) is untouched,
and so is its generator. `RND n` (25214) is:

```python
def lib_rnd(n):                   # n: the argument, 16 bits
    h = lib_mul((seed + 1) & 0xFFFF, 77)   # the library multiply, quirks and all
    if h == 0:
        h = 78
    seed = (h - 1) & 0xFFFF
    return mag(seed) % mag(n)     # 24911's remainder: 0 .. n-1
```

The seed and n are treated as signed by the multiply and divide: a seed of
32768 or more counts as negative, so its magnitude is used, and so is
`seed + 1`'s when that has bit 15 set.

`RANDOMIZE` (25598) sets the seed to FRAMES AND 32767: the low word of
the frame counter, top bit cleared. It runs at the start of every game (the
game-over path jumps back to 25598), so the seed depends on how many frames
have passed since power-on. The game calls RND with constant arguments
only: 5, 8 and 7 at a new game, 2 and 60 when a monster starts.

## The variables

Variables are 16-bit words from 41015, allocated in order of first
appearance in the program: 41015 is the first statement's (`LET control =
2`), the arrays follow, then the scalars from 41277 (x, the FOR at 25606) in
the order the program first uses them; the run of LETs at 25879-26035 is in
address order.

An array's element i (from 1) is the word at `base + 2*(i-1)`. There are no
bounds checks. A constant index is folded into a plain address
(`LET door_room(2) = 18` at 26378 is `LD (41073),HL`), so an array's
elements also appear as scalars. The arrays, from the bases the code
indexes and where the next begins:

| Base | Elements | Name in the listing |
|---|---|---|
| 41017 | 19 | ingr |
| 41055-41203 | 4 each, 18 arrays | the monster slots: m_type, m_steps, ... |
| 41071 | 6 | door_room |
| 41211 | 6 | key_at |
| 41223 | 7 | key_spots |
| 41237 | 6 | keys |
| 41249 | 6 | door_at |
| 41261 | 4 | door_gfx24 |
| 41269 | 4 | door_gfx32 |

(41071 sits among the monster arrays; each run of 4-element arrays is
8 bytes apart.)

The strings PRINT uses are in a pool after the variables (41575-41589), each
printed by address and length. There are no string variables.

## The program's shape

- 25592: `LET control = 2`, then the new-game set-up at 25598 (objects,
  variables, the keys' places), GOSUB 31988, GOTO 30454.
- 30454: BORDER 0, CLS, the menu (39828), then the house scene (26691),
  which ends by walking the hag out into the landscape (27016).
- 30489-30748: the main loop, one pass per move: the hag (27154), doors,
  monsters (34517), scrolling (28731), the chimney smoke, until the game is
  over (40156) or finished (40977).
- Below ground is its own loop (35688-36486), entered from a door through
  32569.

[logic-outline.md](logic-outline.md) indexes the subroutines. Every
subroutine is reached by GOSUB; the compiled code has no computed GOTO, and
it calls hand-written machine code only through USR, with parameters in the
printer buffer (23296-23297) and results in NMIADD (23728-23729, unused on
a 48K).

## The decompiler

`tools/decompile.py` executes the compiled code symbolically: registers and
the stack hold expression trees, each instruction the generator uses is
modelled, and a statement ends at a side effect that leaves the stack
empty. An instruction it doesn't model, an unknown register, or an empty
POP prints the statement as raw `Z80:` lines. Templates match NEXT and the
HALT loop; passes merge FOR's four stores and a PRINT's items. Names come
from `tools/decompile_names.py`.

Each run checks itself:

- the bytes decompiled and the bytes printed raw add up to the whole
  region;
- with execution maps (`tools/zx.py --map`), every executed address in the
  region is an instruction start of the decompiler's disassembly;
- every statement that stores or branches is run on the Z80 from random
  variables (SkoolKit's simulator, the original's own code and library) and
  its effect compared with its expression tree evaluated by the Python
  model of the library. Statements that call machine code (USR), read
  INKEY$ or IN, or draw (25431's drawing; its block stores are checked)
  can't be checked this way.

It reports its figures on every run and fails if a check fails.
