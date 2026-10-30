# Graphics: how each thing is drawn, and colour

How the original puts each thing on screen, how the outdoor scroll works,
and how it uses colour. Addresses are decimal, the original's; the data
formats are in data.md, the routines' contracts and costs in runtime.md.
`tools/zxgfx.py` draws the graphics as PNG sheets in `build/gfx/`, and its
`--check` proves the landscape and room formats here against the
original's own routines (all 61 landscape screens and 64 rooms match,
pixels and attributes). Sample screens, as `.scr` and PNG, are in
`build/screens/`.

## Three ways of drawing

The compiled BASIC draws in three ways, and nothing else touches the
screen:

1. **PRINT through the ROM** (RST 16 and PR-STRING, 8252), with CHARS
   (23606) switched to one of the game's three character sets and back
   to the ROM's afterwards. The panel, the moon and stars, the menu, the
   texts, the cottage's scrolls and the whole outdoor landscape are
   printed. Colour comes from PRINT's INK and BRIGHT control codes.
2. **Its own character blitter** for the underground rooms (45710),
   which writes glyphs and attributes straight to the screen.
3. **SPRITE (25431)**, XOR without a mask, for everything that moves:
   the witch, the enemies, shots, objects. 

There is no back buffer and no frame sync: everything is drawn straight
to the display while it is being shown.

## The screen's layout

| Character rows | Outdoors | Underground |
|---|---|---|
| 0-3 | The panel | The panel |
| 4-15 | Sky: stars, the moon at rows 7-11, columns 6-11 | The room |
| 16-22 | The landscape | The room |
| 23 | Unused (white on black, empty) | Unused |

The upper screen is 22 rows to BASIC; the game sets DF-SZ (23659) to 0
while printing a landscape column so that row 22 can be printed, and
back to 2 after. Sprites use PLOT coordinates, so their y can reach no
lower than pixel row 175, the bottom of row 21.

## The panel

Printed by 55569-55640 from strings at 55641 and 55977, with the panel
font (CHARS 55874):

- **Two scrolls**, 7 x 4 characters of INK 6 at columns 0 and 25 (glyphs
  `!` to `[`, the middle `*` repeated).
- **The labels**: SCORE (row 0, column 9) and MAGIC (row 2) in INK 3,
  HAGS (row 0, column 20); the score's seven digits at row 1, column 8
  and the magic's percentage at row 3 in INK 5. The font draws O as a
  zero, so the texts spell zero for O throughout (`SC0RE`).
- **Changing figures** are printed in place by the compiled code: the
  score, the magic (the string at 41579), the hags left as green strokes
  under HAGS, and a collected key's glyph (the strings at 41575).

Outdoors the panel is BRIGHT; underground the game sets BRIGHT 0 and
reprints it (35546), so the same panel is dimmer below ground.

## The outdoor scene

### The sky

The moon is 6 x 5 characters of the panel font (glyphs `\` to `s`) at
rows 7-11, columns 6-11, and the six stars are the glyph `z` at fixed
cells (6,2), (8,1), (7,16), (14,20), (12,24) and (9,28), all printed
BRIGHT INK 7 from the string at 56024 by 55565. The sky does not
scroll: the scroll moves only rows 16-23.

### The landscape

Built of **columns**: one byte of the map (57310) is a column id, and a
column is 7 character cells, rows 16-22, each with its own ink. The
column table (60430, 14 bytes an id) holds 7 pairs (ink, character code).
Ids below 216 print with landscape font A (CHARS 63744), ids from 216
with font B (CHARS 64512). 255 ids, 248 of them used by the map.

57130 prints one column: for each of the 7 rows, `INK n`, `AT row,col`,
the character, all through RST 16. So a column costs the ROM's full
PRINT path, 7 times: 29674 T-states with font A, 38436 with font B
(`tools/zxprobe.py cost`). 57228 prints 32 of them for a whole screen:
1237471 T-states, 17.71 frames.

The map is 61 screens of 32 columns, and wraps: the witch flying right
off screen 60 comes back to screen 0 (data.md). `build/gfx/landscape.png`
draws all 61. The doors to the underground are columns of it (red doors
at screens 8 and 14, magenta 28, green 41, the cyan crypt at 49), and so
is the cottage (screen 36, where a game starts).

**The keys** lying on the landscape are not part of the map: when a
column is printed, the scroller checks the key positions (41211) and
prints a key's two glyphs (41575, 41576) at rows 20 and 21 in its
colour (29358).

### How the outdoor scroll works

**A push scroll of a whole screen, a character at a time, with the game
stopped.** When the witch reaches the screen's edge, the compiled code
(28746) runs 32 steps, then puts the witch back at x=8 (going right) or
x=224 (going left) on the new screen. Each step:

1. **Shift the bitmap of character rows 16-23 one byte** (57042 left,
   57066 right): a LD loop over 31 columns x 64 pixel rows, column by
   column. 100627 T-states left, 116499 right.
2. **Shift their attributes one cell** (57092, 57111): 11374 T-states.
3. **Print the new column** at column 31 (going right) or 0 (57130),
   reading its id from the map, and a key if one lies there.

A step is about 2.1-2.3 frames, so the 32 steps take about 70 frames
(the long pass in `tools/zxprobe.py pace`'s scroll run is 80.81 frames).
It is a smooth-ish character scroll at 8 pixels a step, about 22 steps a
second, during which nothing else moves; the sprites are erased before
and redrawn after. Being unsynchronised, a step can be seen half done.

The map pointer (41329) holds the address before the leftmost column on
screen; a step right reads (pointer+33) and adds 1, a step left reads
(pointer) and subtracts 1. At 59293 going right it jumps to 57341, and
at 57309 going left to 59261: the 64 columns at the map's end repeat
the first 64, so the jump is invisible.

Unused code beside it scrolls 4 pixels at a time with RLD/RRD (56964,
57005): a finer scroll was tried and dropped.

### What else is drawn outdoors

The witch, bats, ghosts, pumpkins, and the other moving things are
sprites. Each pass, after drawing them, the game puts back the
attributes their colour has spoiled (below).

## The underground

### Rooms

A room is 5 rows x 8 **blocks**, each block 4 x 4 characters, so 32 x 20
characters at rows 3-22 (no room draws in row 3: every block placed in
the top row of a room is blank in its own top row). A block (45980, 24
bytes) is 4 rows of 2 x (inks, character, character): the first
character takes the high nibble of the inks byte as its ink, the second
bits 0-2, and both are BRIGHT on black. Character 32 is skipped, keeping
the room's background.

45710 draws a room: it clears rows 4-23 (rows 4-7 by drawing glyph 32 in
all 128 cells, then the rest with LDIR), sets their attributes to
(23297) (5, cyan on black, in play), then draws each block's characters
with its own blitter: 8 bytes from the underground font (glyph c at
59074 + 8c, set in the word at 45970), one per pixel row, and the cell's
attribute. Room 4 takes 388049 T-states, 5.55 frames.

64 rooms, 74 block types, glyphs 33-127. `build/gfx/rooms.png` and
`blocks.png` draw them. The rooms come in looks: green brick (rooms 4-5,
22-47), red rock with cyan ledges and a red floor (0-3, 6-18, 20-21), the
same with blue water (48-63); room 19 is empty.

### Sprites underground

The witch walks, the enemies (skeletons, bats, frogs, ...) are sprites.
Their attribute modes differ from outdoors (below).

## Sprites

All moving things go through SPRITE (25431); runtime.md has the routine.
The parameter blocks in use (24759 + 8n):

| Block | Use |
|---|---|
| 24767, 24775 | The witch: draw, erase |
| 24783, 24791 | An enemy or object: draw, erase |
| 24799, 24807 | Another: draw, erase |
| 24759, 24815 | Set at start-up to 45246 and 45174 (objects) |

The graphics, with their sizes, are listed in data.md and drawn in
`build/gfx/sprites.png`: the witch flying (8 frames, 24 x 24 pixels) and
on foot (12 frames), bats (16 x 24), ghosts, pumpkins, skeletons, frogs,
skulls, bones, the ingredients, shots (8 x 24). The object types table
(42282) pairs each enemy or object graphic with its rows, width, ink and
frame count.

## Colour

### How attributes are used

- **PAPER is black everywhere**, outdoors, underground, panel and menu.
- **No FLASH** anywhere.
- **BRIGHT** outdoors on everything printed (the landscape is printed
  under ATTR-P 69, BRIGHT with PAPER 0, so each column cell is
  `64 + ink`); underground on the room's walls and ledges, while the
  room's empty cells are 5 (cyan, not BRIGHT) and the panel is not
  BRIGHT.
- **Ink per cell** carries all the colour: one ink per 8 x 8 cell.

### Attribute clash: sprites and the background

**Outdoors**, sprites use mode 2: every cell a sprite covers takes the
print colour, ATTR-T. The witch is drawn with ATTR-T 69 (BRIGHT cyan)
and erased with 71 (BRIGHT white), as are the bats; so a sprite turns
the cells it covers its colour, landscape included, and erasing leaves
them white. The game repairs this every pass: 51687 copies back the
landscape's attributes for rows 16-21, saved by 51675 right after the
landscape was printed, and 52852 restores the moon's 30 cells. Between
the repair and the next draw, the cells under a sprite show its colour:
the witch over the cottage or a tree turns those cells cyan, the classic
clash, for as long as she is there.

**Underground**, sprites use modes 0 and 1 against ATTR-P 5: an enemy
colours only the background cells it covers (those still 5) with its
own ink (7 white for the skeleton, 5 cyan for bats, 2 red, 4 green from
the type table), and its erase puts back 5 only where its ink still is.
On a wall or ledge it takes the wall's colour. The witch is drawn in
mode 1 with an attribute (67) no cell has, so she changes no attributes
at all: she is cyan on the background and the wall's colour over walls.

### Figures

From `tools/zxprobe.py colours`: the 61 landscape screens each printed by
57228 into the flight screen (so with the panel, moon and stars, and
whatever sprites the flight snapshot had in the sky), and the 64 rooms
each drawn by 45710 into room 4's screen.

Cells by attribute, all screens together:

| Outdoors (61 x 768 cells) | | Underground (64 x 768 cells) | |
|---|---|---|---|
| white on black BRIGHT | 28996 | cyan on black | 36296 |
| green on black BRIGHT | 7243 | yellow on black | 3584 |
| yellow on black BRIGHT | 3531 | green on black BRIGHT | 2715 |
| red on black BRIGHT | 2006 | red on black BRIGHT | 2702 |
| white on black | 1952 | cyan on black BRIGHT | 2105 |
| cyan on black BRIGHT | 1561 | magenta on black | 896 |
| magenta on black BRIGHT | 1007 | green on black | 512 |
| blue on black BRIGHT | 552 | blue on black BRIGHT | 342 |

Pixels by colour (lit and unlit pixels of each cell counted as its ink
and paper):

| | black | green | yellow | white | cyan | magenta | blue | red |
|---|---|---|---|---|---|---|---|---|
| Outdoors | 2436722 | 217271 | 172362 | 71694 | 27314 | 26360 | 24552 | 21997 |
| Underground | 2629913 | 146843 | 178688 | - | 85343 | 26112 | 10944 | 67885 |

Distinct colours on one screen, black included: outdoors 6 (8 screens),
7 (45), 8 (8); underground 5 (29 rooms), 6 (21), 7 (14). The most
colours in one character row, rows 0 to 23: outdoors
`3 4 4 3 1 1 2 2 2 2 2 2 3 3 2 2 4 4 4 4 4 5 3 1`, underground
`3 4 4 3 3 3 3 3 3 3 3 3 3 3 3 3 3 3 3 3 3 3 4 1`.

The landscape on its own (rows 16-22, from the column data): the inks
other than black per screen are red and green on 30 of the 61 screens,
blue alone (lakes) on 5, blue, red and green on 7, and up to five
(red, magenta, green, cyan, yellow at the cottage and the graveyard's
gates) on 6. The rooms' inks: green and cyan (27 rooms), red and cyan
(21), blue, red and cyan (14).

**For the BBC's mode.** The panel needs black, yellow, magenta, cyan and
green (4 colours in a row at most, rows 1-2). The sky needs black and
white, plus the sprites' cyan. The landscape needs black plus two inks
on half the screens and up to five on a few, with up to 5 colours in one
character row. The rooms need black plus two or three inks, and the
background cyan. Black paper everywhere, and colour by the 8 x 8 cell,
means the original's look is "ink on black per cell": MODE 1 with one
palette per band (panel, sky, landscape) fits most outdoor screens but
not the cottage or graveyard screens; MODE 2 fits all at half the
horizontal resolution. These are figures for Matt's decision, not the
decision.

## Fonts and character sets

| CHARS | Glyphs (codes 32-127) | Used for |
|---|---|---|
| 15360 | ROM | Restored after each use |
| 55874 | 56130-56897 | The panel, the moon and stars, the cottage's scrolls, the menu, the game-over and ending texts |
| 63744 | 64000-64767 | Landscape font A, column ids 1-215 |
| 64512 | 64768-65535 | Landscape font B, ids 216-255 |
| (59074) | 59330-60097 | The underground blocks, by 45710's own blitter (CHARS is not changed) |

UDG (23675) is left at 65368, where font B's codes 107-127 are: the game
never prints a UDG.
