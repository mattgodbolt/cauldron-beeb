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
