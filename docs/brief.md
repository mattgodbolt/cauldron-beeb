# Cauldron for the BBC Micro: a project brief

*Written on 2026-10-30, after the first research and before the game's
logic is ported. The research behind it is in `docs/research/`; the
decisions are in `docs/decisions.md`.*

How to read the tags:

- **[measured]**: we ran it or read the bytes on 2026-10-30; the tool is
  named in the research file cited.
- **[inferred]**: our reading or arithmetic. Check it before relying on it.

Addresses are the original's, in decimal, as its own code and the POK
file give them.

---

## In short

- **The original is compiled BASIC** [measured, `compiler.md`]. Palace's
  Spectrum *Cauldron* (Ramjam: Tony Barber, Simon Dunstan; ZXDB says the
  compiler was Phipps Associates') is an integer BASIC program compiled
  to Z80. Around it are the compiler's runtime library (its arithmetic
  and one XOR sprite routine) and a little hand-written machine code (the
  landscape's printing and scrolling, the rooms' blitter, text screens,
  the control reader).
- **So the specification is a BASIC program.** `tools/decompile.py`
  turns every byte of the compiled code (25592-41014) back into BASIC
  statements, `build/cauldron.bas`, with nothing left raw, and checks
  each statement that stores or branches against the Z80 running it.
  The port transcribes that listing, statement by statement.
- **The game is slow and simple to draw.** No frame sync: about ten
  passes a second, slower with more sprites [measured, `runtime.md`].
  The outdoor scroll is not a scroll but a push: at the screen's edge the
  game stops and slides a whole new screen in, a character at a time
  [measured, `graphics.md`]. The rooms are flip screens.
- **Colour fits MODE 1.** Paper is black everywhere and the colour is
  one ink per cell. Three inks per landscape screen keep 99.33% of the
  landscape's lit pixels in their own colour, and three per room keep all
  of the rooms' [measured, `tools/colourstudy.py`]. Decisions 2 and 3
  (provisional) take MODE 1 at the Spectrum's 256 x 192 with a palette
  per band, chosen per screen and per room.
- **It fits a B with 16K of sideways RAM** [inferred]. The original's
  data is about 24K (41575-65535, less the hand-written code), much of it 1-bit graphics; the compiled code is
  15K of very loose code that 6502 should carry in less.
- **Done so far:** the harness on both machines, the research, the
  screen in the Spectrum's geometry, the data in sideways RAM, and every
  landscape screen and room drawn and checked byte for byte against the
  original's (`make check`).

---

## 1. What the original is

ZXDB entry 850, Palace Software, 1985: a 48K Spectrum game. ZXDB credits
Steve Brown, Tony Barber and Simon Dunstan. The TAP's BASIC loads the
loading screen and a headerless block at 24600-65535, waits for a key and
calls 24600 (`make zx` runs it there).

The memory map (`data.md`):

| From | To | What |
|---|---|---|
| 24603 | 24822 | The compiler's workspace: FOR slots (one per letter), the eight sprite parameter blocks |
| 24823 | 25591 | The runtime library: arithmetic, comparisons, RND, INKEY$, PEEK, POINT, SPRITE (25431) |
| 25592 | 41014 | The compiled BASIC |
| 41015 | 41574 | The variables, a 16-bit word each |
| 41575 | 65535 | Strings, tables, object types, rooms, blocks, sprites, fonts, the landscape's map and columns, and the hand-written code among them |

The original has almost no free space.

## 2. How it plays (`logic-outline.md`)

- **The front end**: a menu (Kempston, Sinclair II, keys CAPS SHIFT to
  V, play), then the house scene: the hag walks into her cottage, stirs
  the cauldron and walks out.
- **Above ground**, the main loop (30489-30748): the hag flies or walks
  over a landscape 61 screens wide that wraps. She lands only on grass;
  trees knock her off her broom. Bats, ghosts, pumpkins and the like
  spawn every few passes; her spell costs magic; at the screen's edge the
  view is pushed on a screen. Four coloured keys are hidden in the
  landscape, and each opens the door of its colour.
- **Below ground**, its own loop (35688-36486): 64 flip-screen rooms in
  caverns behind the doors. The hag walks and jumps between ledges for
  the six ingredients (and the chest and the bag).
- **The end** [inferred, from the inlay and the outline]: the six
  ingredients go into the cauldron for the spell against the pumpkin.
  Losing all the hags ends the game. The completion path (40977) is
  decompiled but not yet read closely.

## 3. How it works underneath

**Random numbers** (`compiler.md`): RND keeps its seed in DEFADD (23563)
and steps it as `seed = mul(seed + 1, 77)`, 0 becoming 78, then less 1,
returning `|seed| mod |n|`. The multiply is the library's, and its carry
leaks into the multiplicand, so it isn't a true product: the port
copies it bit for bit. RANDOMIZE seeds from FRAMES at each new game. For
the comparisons the port and the original take the same seed.

**Drawing** (`graphics.md`): three ways.

1. ROM PRINT with the game's own fonts: the panel, the moon and stars,
   the texts, and the landscape, printed a column at a time from a
   column table (7 cells of ink and character per column id).
2. Its own blitter for the rooms: 5 x 8 blocks of 4 x 4 characters.
3. SPRITE, in the compiler's library: XOR, unmasked, a pixel row at a
   time through the ROM's PIXEL-ADD, recolouring the cells it covers.
   Outdoors it turns every cell under a sprite its colour (the witch
   cyan), and the game puts the landscape's colours back each pass;
   underground an enemy colours only background cells, and the witch
   none.

**The push scroll**: 32 steps, each shifting rows 16-22 a byte and their
attributes a cell, and printing the new column: about 2.3 frames a step,
with the game stopped [measured].

**The frame**: no HALT. A pass is 4-8 frames, median 5.25 standing and
7.77 firing outdoors, 3.92 underground [measured, `tools/zxprobe.py
pace`]. Sprites and their attributes are over half the time outdoors.

**Sound**: the ROM's BEEPER only, with the game stopped: a rising chirp
when the witch shoots something, a falling one when she is hit, and the
menu's click. 21 steps of two cycles each, 16 and 23 ms [measured].

## 4. The BBC: what fits

**Screen**: MODE 1, 256 x 192, 12K at the top of main RAM (decision 2).
The bands (the panel, rows 0-3; the sky, 4-15; the landscape, 16-22; or
the room, 3-22) each get a palette by splits in the interrupt
(decision 3). The panel needs five colours, four at most in a row, so
it may take a split a row.

**Memory** [inferred]: main RAM from `&0E00` (once the game owns the
machine) to the screen is about 16.5K; the sideways bank 16K; pages
`&04-&0D` some more. The landscape, rooms and fonts take 13.7K of the
bank today. The sprites (about 6.5K of 1-bit frames), the panel font
and the texts still have to go somewhere, and the code: the BASIC is
15K compiled, but each statement compiles to a dozen loads and stores
of 16-bit words that 6502 needs a fraction of. Main RAM holds the code
and the sprites; the bank the rest.

**Speed** [inferred]: the original is slow, so the BBC has room. The
cost is the sprites: an unmasked XOR of a 24 x 24 sprite on a 2MHz 6502,
with the 1-bit graphic expanded to MODE 1 as it goes, is a few thousand
cycles; pre-expanded frames would trade memory for speed.

## 5. Decisions to make

Taken, provisionally (`decisions.md`): **1** the original is Palace's
TAP; **2** MODE 1 in the Spectrum's geometry; **3** a palette per band,
per screen and per room.

Matt took the recommendations below (2026-10-30): decisions 6-9.

Open until then, with a recommendation:

- **D4. The pace.** The original has no frame sync, so its speed is how
  long each pass took a 3.5MHz Z80: 4-8 frames. A BBC running flat out
  would run at its own, different speed. Options: (a) a fixed pass
  length on VSync, from the original's medians (5 frames outdoors, 4
  underground); (b) a pass length that follows what the original would
  have spent (sprites drawn, monsters moved), modelled from the
  measurements; (c) flat out. **Recommend (a)**, measured and tuned
  against the original's play; (b) if (a) feels wrong with many sprites
  on screen.
- **D5. The push scroll's pace.** Keep the push, as the original's
  design, at its measured 2.3 frames a step (each step on VSync).
  Hardware scrolling can't move a third of the screen alone.
- **D6. Sprite colours.** Settled: cyan is kept as logical 2 below the
  panel for the sprites (decision 4), and Matt chose no colour clash
  (decision 5), with the attributes and the lit pixels kept exactly for
  the logic.
- **D7. Sound.** The chirps as SN76489 tones at BEEPER's pitches, a tone
  a step at the step's length; and keep the game stopped while they
  play, as the original does. The menu's click as a short tone.
- **D8. Controls.** The original's keys are CAPS SHIFT, Z, X, C and V
  (its menu says "keys CS to V"), with Kempston and Sinclair joysticks.
  On the BBC: Z, X, :, / and RETURN by default, redefinable, and an
  analogue joystick. Matt to choose.
- **D9. Speed-ups that change nothing.** The original's work is slow by
  design (its compiler), and none of its slowness is visible except
  as pace (D4). The port can draw sprites by its own means as long as
  the screen matches.

## 6. The order of work

1. **Screen** (done): the geometry, the bands to come.
2. **Data** (done for the landscape and rooms): the sprites, the panel
   font and texts next.
3. **Drawing**: the landscape and rooms (done, checked); the panel, the
   moon and stars, the splits; then SPRITE, with the outdoor and
   underground attribute rules, checked against SPRITE run headless on
   the same blocks.
4. **The hag**, transcribed from `hag_pass` and its subroutines, checked
   pass by pass against the original with the same keys (`make passes`,
   as CE2's).
5. **Monsters**, then **objects, keys and doors**, then **below ground**.
6. **Sound**, the **front end** (menu, house scene), the **loader**.

Agents can split the logic by `logic-outline.md`'s five parts, each
transcribing its own subroutines from `build/cauldron.bas`.
