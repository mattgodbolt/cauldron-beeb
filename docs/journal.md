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

### SPRITE, and no clash

SPRITE (25431) first went in with the original's clash: when a cell's
attribute changed, its lit pixels were recoloured, which kept the BBC's
screen the Spectrum's with its colours mapped. Matt preferred no clash
(decision 5), so it changed before anything was built on it: the
attributes are still kept exactly, and the lit pixels, but a pixel's
colour comes from whether the scenery has it lit (each cell's glyph and
colour, noted as the scenery draws it).

`make sprites` (tools/spritecases.py, tools/spritecheck.mjs) runs random
calls on both machines: 300 cases, 309 calls of them past column 31,
all match. The bugs it found: a region table built with comparisons
(baron's TRUE isn't 1); CAULDAT loading over the code once the sprites
grew it; the wrap past column 31, which carries into the next character
row of the third and from a third's last row into the pixel line; a
carry left set between pointer additions, which left the last scene's
colours in the cell tables (it showed only when one case followed
another: the cases had been run alone first).

The code outgrew `&1900-&5000` with the sprites in it, so CAULDRN is now
CE2's shape: the game assembled at `&0E00`, loaded at `&1900` with a
loader after it that puts CAULDAT in the bank and TITLE in the screen and
then copies the game down over the DFS's workspace. The workspace
(`attrs` and the tables) comes after the code and isn't in the file.

Memory will be the next constraint: the logic's code and its tables are
still to come, beside the 1-bit graphics in main RAM and a nearly full
sideways bank. The memory map wants planning before the hag.

### The logic, compiled again

Matt took the brief's recommendations for the pace, sound and controls
(decisions 6-9), the keys the usual BBC ones (Z, X, :, /, RETURN).

The logic is 1345 BASIC statements. `tools/zxranges.py` measured each
variable's range in random play outdoors and through each door, and a
native compiler using them (bytes where they fit) came to 18.4K: too
big. The same trees as bytecode come to 9.9K (decision 10). The
interpreter (`src/vm.6502`) works in the original's address space,
translating PEEK and POKE at run time (`src/vmxlat.6502`), and calls the
original library's semantics (`src/basrt.6502`), transcribed: the
multiply's loop is the Z80's instruction for instruction, since the
6502's ROR and ROL keep the carry where RR and RL do.

`make vm` (`tools/vmcheck.py`) runs each statement on py65's 6502 and on
the Z80 from the same random variables: 1236 agree, the rest wait for
what the layers bring (sprites, PRINT, the USR routines, ATTR and POINT,
the data tables' addresses). It found a branch reading flags a load had
replaced (NEXT), and two things of its own: statements with no bytecode
share their label with the next, and RANDOMIZE reads FRAMES, which it
hadn't copied.

### The original's program, running

With the interpreter in the game (decision 11's two banks), the
original's BASIC runs from its entry: the start-up, the menu (its
INKEY$ loop waiting for 1 to 4), the house (the hag walking in and
stirring), the walk out of the door, and the main loop outdoors, bats
and all, on the B and the Master. What it took besides: PRINT as the
ROM's (`print.6502`: a state machine over the channel, TEMPS and PERM,
the fonts CHARS names); the USR routines for the scenery, the room, the
attributes' save and restore, the moon, the texts, the controls (the
original's table for its keys, on the BBC's) and a landscape screen
(57228); the logic's tables in their bank, the landscape map PEEKed in
the data's, and the Spectrum's bitmap PEEKed from the port's screen.

Two things the loader had wrong: the OS pages its own ROM back after
`*RUN`, so the game pages its data bank itself; and the palette splits
for the lower band were set only by the landscape and the rooms, so
the menu's showed stripes.

The menu's colours are the game screen's bands, which don't suit it:
the front end's own layer will give it its own.

### Pass by pass

`make passes` plays the original and the port side by side
(`tests/scenarios.txt`: keys held over passes), RND's seed set the same
just after RANDOMIZE, and compares every variable at the top of every
main-loop pass. The port's side runs the test disc (`-D VMBRK=1`): the
interpreter calls `vm_hit` at a chosen statement and `vm_pass` as each
pass begins, where decision 6's pace waits.

The first run found the port's variables uninitialised (the original's
are zeros on the tape). After that every pass the port runs agrees:
standing, flying each way, firing, the bats coming and hitting. Each
scenario that flies to the edge stops at the push scroll's machine code
(57042, 57066): the next layer.

### The push scroll

The landscape's machine code (56900 on) as the port's: the column
printer (57130) through the port's PRINT, so its attributes are
PO-ATTR's from the current colours as the original's are; a whole
screen (57228) as 32 of those; the bitmap's and the attributes' pushes
(57042, 57066, 57092, 57111), the cells' scenery tables (decision 5)
pushed with the pixels. During a push the view holds two screens: the
lower band's palette follows the view's middle column (the BASIC's own
map pointer says where it is) and the band's cells are recoloured when
it changes screen, which is exact since no sprite is on screen then.
Every scenario's passes now agree with the original's through the
scrolls.

`tests/scenarios.txt` can now set variables on both machines as a pass
begins (`=ADDR:VALUE`, or `@ADDR` for each machine's own word there),
to set scenes up: the doors, as the decompiler's exploration did.

### Underground, and the front end's colours

Two door scenarios (all the keys, the witch set at a door, walking in)
take the port underground: every pass agrees with the original's. On
the way: BASIC's AND evaluates both sides, so 38012 reads `ingr(i)` for
an i below the array, into the compiled code's last bytes, which are
now among the logic bank's tables (as nm's monster scan read past its
map).

Matt saw the menu's fourth option vanish (the lower band's colour map,
never set before a landscape or room): the front end has its own layout
now, the original menu's four colours exactly. And the doors' graphics,
moving scenery, take their cell's colour as the original's do
(decision 5's exception); the sprite check models it.

### Sound, and the first of the speed

Sound (decision 8): BEEPER's chirps on the SN76489 at BEEPER's pitch
(the research's measured half-period, 4p + 118 T-states) for its two
cycles a step, timed on the User VIA's T2; the menu's BEEP middle C for
a tenth of a second.

`tools/passtime.mjs` measures the frames a pass takes on the BBC, and
`tools/sample.mjs` profiles. In flight a pass first took 15-25 frames,
against decision 6's 5: about 40% SPRITE and 45% the interpreter. So
far: the delay loops run at once (decision 12); SPRITE works a cell's
place, scenery and colours out once a character row rather than once a
byte, skips empty halves, and has a fast way over blank background.
That took the median pass from 770K cycles to about 480K: still more
than twice the 200K of 5 frames. The interpreter's dispatch and its
stack are next.

Memory ran out on the way (the game's file ran into the screen):
tables of the column records' and the rooms' and blocks' addresses
became arithmetic, and the sprite regions lost the machine code and
buffers among them. A bug found by `make sprites`: `sprite_byte` stored
a value in a file-level ZA_AUTO before calls whose locals the allocator
may share it with; calls first, stores after, is the safe order.

### The screen in play, and the faster interpreter

`make passes` now compares the screen too, every 10th pass: each
pixel lit or not, and the attributes, which the port keeps as the
original's. It found the first monster: drawn before its mode is ever
set, in mode 0 with attribute 0, black on black, so the port coloured
its pixels black, which on the BBC is unlit, and its erase then went
wrong. A black sprite now takes ATTR_T's ink (decision 5). Matt saw the
witch leave her colour on the cottage on the published disc: the door
before decision 5's door rule.

The interpreter: superinstructions for an array's element by a
variable index (load and store) and adding a byte constant, the sprite
blocks' addresses folded, dispatch through a page-aligned table, and
sprite rows shifted at most 4 times: a pass in flight about 348K
cycles, from 480K (5 frames: 200K).

### Native code for the hottest statements

`tools/zxhot.py` counts each statement's runs a pass on the original:
about a thousand runs a pass, the 200 most run statements 82% of them.
`tools/bas2native.py` compiles a statement of stores or an IF to a
native routine in the logic bank, words throughout (no typing from
ranges: what the bytecode does, faster), through the interpreter's own
memory and arithmetic routines; the bytecode calls it (NATIVE, NIF).
`make vm` checks them against the Z80 like the rest. 80 fit the logic
bank (`NATIVE` in the Makefile); a pass in flight from 332K cycles to
304K. `tools/vmcheck.py` used to run the compiler itself without the
native options, so it checked bytecode the disc didn't have: it uses
the Makefile's now.

### SPRITE a character row at a time

The fast path now works a character row's rows together
(`sprite_segment`): each row shifted into `seg_buf`, the cells cached
once, then each cell down its lines with Y the line, every half-byte
through tables (`mask_of`: the colour mask from the scenery's pixels;
`half_at`: the XOR, keeping what the sprite's pixels leave alone).
Rows of the sprite's buffer that are blank skip the cell. The pass in
flight from 304K cycles to 291K median (5 frames is 200K).
`make sprites` and `make check` agree.

### SPRITE's colours read the wrong bank

A brainstorming agent found that `op_sprite` called SPRITE with the
logic bank paged, while the scenery glyphs decision 5's colour rule reads
(`cell_bg`: landfont, underfont, panelfont) are in the data bank. In
play, then, a sprite's pixels over scenery took colours chosen from
bytecode. Lit pixels and `attrs` were right throughout, which is all
`make passes` compares, and `make sprites` runs in the viewer, where the
data bank is always paged; so nothing saw it. `op_sprite` pages the data
bank around the call now. The checks still compare no colours in play: a
gap.

### Constant addresses folded; more native statements

Three brainstorming agents looked for changes of approach (SPRITE's
data and loop, what gets drawn and when, the logic); their plans are in
`docs/speed.md`. The cheapest first: `+` and `-` chains with constant
offsets fold into one constant (`simp` in `tools/bas2vm.py`, used by
`bas2native.py` too), so a SPRITE SET's field stores (`blockaddr(n)+1+1`)
are single STB/STW, mod 2^16 as the original's adds are. That freed
enough of the logic bank for 130 native statements (`NATIVE`). A pass in
flight: about 264K cycles median (5 frames is 200K). `tools/sample.mjs`
charges code in the sideways window to the last label below it
(`no_ram_end`): that's the native statements.

### SPRITE: the three steps of docs/speed.md

1. The half-byte update by table: `S' = S EOR (B AND (S OR (M AND
   nlit[S])))`, `M = own EOR (spread[glyph] AND (home EOR own))`, with
   `hi_spread`, `lo_spread` and `nlit` made at start-up in the workspace
   (in the file they pushed CAULDRN's end into the screen). `seg_buf` is
   by column, read through a self-modified load; the right half has its
   own pointer.
2. The cells set up once per character row, not cell by cell: one
   `cell_at`, the cell tables through pointers sharing `attr_ptr`'s low
   byte, the sprite's own colour once (a door's still per cell, after
   the attributes); `sprite_cache` and its arrays went.
3. The shift straight into `seg_buf` (`seg_row`), a byte at a time in A
   through `LSR A : ROR t` or `ASL A : ROL t` chains entered by a
   self-modified jump; the slow path keeps `sprite_shift`.

A pass in flight: 264K, 248K, 221K, 210K cycles median after each (5
frames is 200K), the fastest passes under it. `make check` passes. Main
RAM's workspace is nearly full now (the tables).

### Native statements chained

A native statement's bytecode is now one `OP_NGO` into its code, and the
code goes on by itself: `JMP G<addr>` to the next statement (or an IF's
target), `G` being that statement's native code when it has some, else a
shared exit (`native_exit`) back to its bytecode. No call and return a
statement, and 92 of the 169 places native code goes on to are native
themselves. `src/vmtest.6502` defines `NOCHAIN` so every statement exits
to the next one's label and `make vm` still checks them one at a time;
`BREAK_AT` keeps the harness's breakpoint statements bytecode. 120 fit
the logic bank. A pass in flight: median 199,680 cycles, the pace itself
(decision 6's 5 frames): most passes now wait for it. The slowest are
still about 279K.

### RND's remainder; the port against the original

`rt_rnd` takes `|seed| MOD |n|` for n a power of two below 256 (RND 2,
RND 8) from the seed's low bits: the restoring divide's remainder
exactly, without it. Small in the end: the heavy passes weren't RND's.
`tools/passtime.mjs` now separates a pass's work from its wait for the
pace (`vm_pass_due`, the test disc's), and the original's passes were
timed the same way: docs/speed.md has the table. The port's work is
under the original's pass in every run measured, standing, flying and
firing; decision 6's fixed 5 frames is what holds it back in flight.

### The pace kept; the README's screenshots

Matt kept decision 6's fixed 5 frames: the port, faster than the
original in flight, holds its pace where the original slows. The README
now has screenshots of the port (`docs/images/`, cropped to the
Spectrum's geometry from `tools/play.mjs`'s) and says what plays.
`tools/beepass.mjs` takes `BEEPASS_SHOTS=n,m` to screenshot those
passes of each scenario it plays.
