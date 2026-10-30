# Journal

How the port got here, in order.

## 2026-10-30

### Starting

Matt set out to port *Cauldron* (Palace Software, 1985) from the 48K
Spectrum to the BBC Micro, run the way *Chuckie Egg 2* and *Ninja
Massacre* were (`../porting-to-the-beeb.md`). The targets are a Model B
with 16K of sideways RAM and the Master 128, from one disc, as for CE2
and nm.

ZXDB entry 850 has Palace's release as TAP and TZX, Silverbird's
re-release, a full map, maps in parts and POKEs; `make fetch` gets them
(`original/README.md`). The TAP and the TZX hold the same screen and game
blocks. ZXDB says the game was "authored with" Phipps Associates' BASIC
compiler, so some of the code may be compiled BASIC.

The harness came from the siblings: `tools/zx.py` (nm's, with its R
register patch taken out until Cauldron's own random reads are known),
`tools/beeb.mjs` and `tools/play.mjs` (CE2's), `asm.sh`, `grid.py`,
`lint_labels.py` and `zx02.py`.

The TAP's BASIC loads the loading screen to 40000 and copies it to the
display, loads the game to 24600-65535 headerless, returns, waits for a
key (`PAUSE 0`) and calls 24600. `make zx` simulates the load and runs to
24600 with a key held, giving `build/cauldron.z80`.

### The original is compiled BASIC

An execution map of the menu and some flying, and a PC-sampling profile
of flight, show the shape of the program:

- 24880 up is the compiler's runtime library: 16-bit multiply and divide,
  comparisons that leave 0 or 1 in HL, PEEK, IN, INKEY$ through the ROM,
  POINT, and a sprite routine at 25431 that XORs a shifted image onto
  the screen through the ROM's PIXEL-ADD and sets attributes.
- 25592 to about 41000 is compiled integer BASIC: every variable a
  16-bit word at a fixed address, FOR loops keeping their limit, step and
  loop-back address in slots, text printed through the ROM.
- Hand-written machine code is small: print helpers, attribute copies.
- In flight, over a third of the time is in the sprite routine and a
  seventh in the ROM's PRINT.

So the specification of the game logic is a BASIC program, and the first
research tool is a decompiler for this compiler's output
(`tools/decompile.py`, `docs/research/compiler.md`). Two agents started at
once: one on the decompiler and the logic's outline, the other on the
runtime, the drawing, the scrolling, the data and the colours
(`docs/research/runtime.md`, `graphics.md`, `data.md`).

### The screen in the Spectrum's geometry

The first BBC build: `!BOOT` runs `CAULDRN`, which loads `TITLE` with
OSFILE into screen memory, takes the interrupts, sets MODE 1 in the
hardware with the CRTC narrowed to 256 x 192 (CE2's registers) and shows
it. `TITLE` is the loading screen made by `tools/mkscreen.py`, which keeps
the four commonest colours and draws the rest as the nearest of them: a
look at the geometry, not the colour scheme. Converted data is made into
`build/` from `original/` and never committed.

`!BOOT` loading `TITLE` itself failed: the OS echoes `!BOOT`'s next line
into MODE 7's screen at `&7C00`, inside ours. The screen read back from
memory matches the converter's bytes on the B and on the Master.

### Below the BASIC: drawing, data, frame, sound

An agent mapped everything outside the compiled BASIC
(`docs/research/runtime.md`, `graphics.md`, `data.md`,
`disasm/runtime.ctl`). The game draws in three ways: ROM PRINT with its
own character sets (the panel, the sky, and the whole landscape, column
by column), its own blitter for the underground rooms, and one XOR
sprite routine in the compiler's library that recolours cells as it
goes. The outdoor "scroll" is a push of a whole screen, 32 character
steps of shifting the bottom third and printing a new column, with the
game stopped. No frame sync at all: about ten passes a second, more
than half of it in the sprite routine outdoors. Sound is the ROM's
BEEPER: two 21-step chirps and the menu's BEEP.

`tools/zxgfx.py` draws the graphics into `build/gfx/`, and its `--check`
compares its rendering of all 61 landscape screens and 64 rooms with the
original's own routines run headless: they match. `tools/zxprobe.py`
makes the scenes (it reaches the underground by giving the witch a door
and its key at the door test) and measures pacing, profile, routine
costs and colour.

### Decompiling the compiled BASIC

The game logic (25592-41014) is the output of a simple BASIC compiler:
every expression is built in HL with a library at 24880-25591, so
`tools/decompile.py` executes it symbolically rather than pattern-matching,
and `make bas` writes the whole program back as BASIC
(`build/cauldron.bas`). It matches all of the compiled code; anything it
couldn't follow would print as raw Z80. Each statement that stores or
branches is also run on the Z80 from random variables and checked against
its decompiled expression. That caught the first model of the library's
multiply: the library's isn't the true product when a partial sum
overflows (the carry leaks into the multiplicand), and RND depends on it.
The model now copies it bit for bit.

Two finds worth keeping: the FOR slots at 24603 are one per letter, so the
FOR variables keep their source names (x is the hag's x); and a constant
array index is folded into an address, so array elements also appear as
scalars. `docs/research/compiler.md` has the compiler and the RND algorithm
the port must copy; `docs/research/logic-outline.md` maps the program.
Execution maps for the listing's "never ran" marks were made by driving
the original with pokes (teleporting to doors with all keys held); they
live in `build/maps/`.

### Colour, counted

`tools/colourstudy.py` counts the lit pixels of each ink in the
landscape's columns and the rooms' blocks. One palette of three inks per
landscape screen keeps 99.33% of them in their own colour, and per room
all of them; MODE 2 would keep every colour but halve 13% and 17% of lit
pixels' pairs. Decisions 2 and 3 (provisional): MODE 1, a palette per
band, chosen per screen and per room.

### The data in sideways RAM, and the drawing

`tools/mkdata.py` writes the original's tables (the landscape's fonts,
columns and map; the blocks, rooms and underground font) and decision
3's colour maps into `build/data/`. They outgrew `&1900-&5000` beside
the code at once, so the sideways RAM loader came early: CAULDRN loads
CAULDAT at `&3000`, copies it to the highest free bank, which stays
paged in, and says so and stops if there is none.

`src/land.6502` and `src/room.6502` draw a landscape screen and a room
from the 1-bit data, expanding each glyph into its logical colour as it
goes (`src/draw.6502`). The viewer (`src/viewer.6502`, after the title)
steps through them. `make draw` runs `tools/drawcheck.mjs`, which has
the viewer draw all 61 screens and 64 rooms and dumps them, and
`tools/drawcmp.py`, which draws the same from `tools/zxgfx.py`'s readers
(proven against the original's own drawing) through the same colour
maps and compares bytes and palettes. Two bugs on the way: a jump into
the middle of an instruction (`viewer + 3`), and the offset of screens
32 on losing a carry. All match on the B and the Master.

### The scenes: the panel, the sky, and the splits

The panel and the sky are printed through the ROM from strings of INK,
AT and BRIGHT codes (55565 and its other entries), so the port has a
small PRINT (`src/print.6502`) that keeps the Spectrum's attribute file
as it would be (`attrs`): the game logic reads attributes (the grass's 65
under a landing) and pixels (POINT for the trees), so the port's screen
must have the original's lit pixels and its attributes, colour aside.

`tools/zxscene.py` has the original's own code draw every outdoor scene
(CLS under ATTR_P 71, 55565, 57228) and every underground one (ATTR_P 5,
CLS, 55569, 45710), and `make draw` now compares the BBC's whole screen,
its attributes and its colours with those: all match on the B and the
Master. The ROM's CLS gives rows 22-23 BORDCR's attribute, which the
port copies.

Decision 4 lays the splits out so each changes one logical colour (four
ULA writes) where nothing beside it shows that colour. The interrupt
takes a table of splits; `tools/splitsweep.py` builds with each timing
and counts wrong pixels in a screenshot's panel rows: clean from 88 to
116 on both machines, parked at 102.
