# Data: the memory map from 24600 to 65535

What every region of the game's memory is, and the formats of its data.
Addresses are decimal, the original's. The tape loads 24600-65535 in one
block; nothing is unpacked or moved, so the snapshot at the game's entry
(`build/cauldron.z80`) holds all of it, with the variables and the
runtime's workspace zero.

How regions were found: by the code that reads them (disassembly), and by
running the game on SkoolKit's Python simulator with every memory access
logged against the PC that made it, over the menu, a start, long flights
both ways, random play outdoors and in two underground areas. A region
marked *not seen read* was not touched in those runs; its identity comes
from its look or its neighbours. `disasm/runtime.ctl` carries this map
as SkoolKit blocks, and `tools/zxgfx.py` draws the graphics.

## The map

| Start | End | What | Read by |
|---|---|---|---|
| 24600 | 24602 | `JP 25592`, the entry | the TAP's `RANDOMIZE USR 24600` |
| 24603 | 24758 | Compiler workspace: FOR-NEXT blocks | compiled FOR/NEXT |
| 24759 | 24822 | Eight sprite parameter blocks, 8 bytes each | SPRITE |
| 24823 | 25591 | The runtime library | compiled code |
| 25592 | 41014 | The compiled BASIC (ends `JP 25592` at 41012) | |
| 41015 | 41570 | The compiled program's variables, a word each | compiled code |
| 41571 | 41574 | Unused (zero) | |
| 41575 | 41589 | String literals for PRINT (key glyphs `ty{\|`, the magic's `O`, blanks, `0000`) | compiled PRINT |
| 41590 | 41731 | Small tables (pairs of bytes) | compiled PEEK |
| 41732 | 42139 | Unused (zero) | |
| 42140 | 42168 | Code: print the ending text | USR |
| 42169 | 42279 | The ending text (`WELL D0NE ... L0NG LIVE THE PUMPKIN`) | 42140 |
| 42280 | 42281 | Unused | |
| 42282 | 42449 | Object types: 21 x 8 bytes | compiled PEEK |
| 42450 | 42497 | Sprite graphics: shots, 8 rows x 3 bytes, 2 frames | SPRITE |
| 42498 | 42500 | Unused | |
| 42501 | 43588 | Room records: 64 x 17 bytes | compiled PEEK, POKE |
| 43589 | 43589 | Unused | |
| 43590 | 45317 | Sprite graphics, 24 rows x 3 bytes: skeleton (43590, 4 frames), then 20 frames from 43878 | SPRITE |
| 45318 | 45319 | Unused | |
| 45320 | 45447 | Room entry positions: 64 x (x, y) | compiled PEEK |
| 45448 | 45703 | Room exits: 64 x 4 | compiled PEEK |
| 45704 | 45709 | Unused | |
| 45710 | 45969 | Code: draw a room | USR |
| 45970 | 45973 | The room blitter's font base (word, 59074) and screen pointer (word) | 45710 |
| 45974 | 45979 | Unused bytes | |
| 45980 | 47779 | Underground block types: 75 x 24 bytes (type 0 unused) | 45710 |
| 47780 | 47789 | Unused | |
| 47790 | 50349 | Underground rooms: 64 x 40 bytes | 45710 |
| 50350 | 50387 | Code: print the game-over text (50340-50349 are not code) | USR |
| 50388 | 50549 | The game-over text (`THY QUEST HAS FAILED ...`) | 50350 |
| 50550 | 50761 | The menu | 50369 |
| 50762 | 50781 | Code: open stream 2; select the panel font; the ROM font | 50350, 50369 |
| 50782 | 50799 | Unused bytes | |
| 50800 | 51665 | Sprite graphics: the witch on foot, 24 x 3 bytes: 4 frames at 50800, 8 at 51090 | SPRITE |
| 51666 | 51674 | Unused | |
| 51675 | 51698 | Code: save and restore the landscape's attributes | USR |
| 51699 | 51699 | Unused | |
| 51700 | 51891 | The landscape's saved attributes (rows 16-21) | 51675, 51687 |
| 51892 | 51899 | Unused | |
| 51900 | 52293 | Code: read the controls (Kempston 51926, keys 51991, Sinclair 52088) | USR |
| 52294 | 52299 | Unused | |
| 52300 | 52811 | A door, 32 rows x 4 bytes, 4 frames (*not seen read*) | |
| 52812 | 52819 | Unused | |
| 52820 | 52849 | The moon's attributes, 5 x 6 | 52852 |
| 52850 | 52851 | Unused | |
| 52852 | 52877 | Code: restore the moon's attributes | USR |
| 52878 | 52947 | A small graphic, 2 bytes wide, from 52897 (*not seen read*) | |
| 52948 | 53331 | Sprite graphics, 16 x 2 bytes: 52948 (4 frames), 53076 (4, *not seen read*), 53204 (4) | SPRITE |
| 53332 | 53339 | Unused bytes | |
| 53340 | 53531 | Sprite graphics, 24 x 2 bytes, 4 frames (*not seen read*; the last object type) | |
| 53532 | 53723 | Sprite graphics, 24 x 2 bytes, 4 frames (vertical bars; drawn in the witch's sprite block) | SPRITE |
| 53724 | 53729 | Unused | |
| 53730 | 54113 | Sprite graphics, 16 x 3 bytes: bats (53730, 4 frames), 53922 (4, *not seen read*) | SPRITE |
| 54114 | 54119 | Unused | |
| 54120 | 54695 | Sprite graphics: the witch flying, 24 x 3 bytes, 8 frames | SPRITE |
| 54696 | 55559 | Sprite graphics, 24 x 3 bytes, 4 frames each: ghost (54696), an explosion (54984), pumpkins (55272, *not seen read*) | SPRITE |
| 55560 | 55564 | Unused | |
| 55565 | 55640 | Code: print the moon and stars, the cottage's scrolls, the panel | USR |
| 55641 | 56096 | Their strings | PR-STRING |
| 56097 | 56129 | Unused | |
| 56130 | 56897 | The panel font (CHARS 55874), codes 32-127 | ROM PRINT |
| 56898 | 56932 | Unused bytes, and a list ending 255 at 56920 | compiled PEEK |
| 56933 | 57041 | Code, not used: remains of a 1-pixel scroll; 4-pixel scrolls (56964, 57005) | |
| 57042 | 57253 | Code: the landscape's scroll and print | USR |
| 57254 | 57309 | Unused (zero) | |
| 57310 | 59325 | The landscape map: 2016 column ids | 57130, 57228, compiled PEEK |
| 59326 | 59329 | Unused | |
| 59330 | 60097 | The underground font, codes 32-127 (glyph c at 59074 + 8c) | 45710 |
| 60098 | 60099 | Unused | |
| 60100 | 60339 | Sprite graphics, 24 x 2 bytes, 5 frames | SPRITE |
| 60340 | 60429 | Column ids, 90 bytes (*not seen read*) | |
| 60430 | 63999 | Landscape columns: 255 x 14 bytes | 57130 |
| 64000 | 64767 | Landscape font A (CHARS 63744), codes 32-127 | ROM PRINT |
| 64768 | 65535 | Landscape font B (CHARS 64512), codes 32-127 | ROM PRINT |

Outside the block: the game passes parameters to its machine code in
the printer buffer (23296-23297), the control reader answers in 23728
(direction) and 23729 (fire), and RND keeps its seed in DEFADD (23563).
The game runs in IM 1 and needs none of the space from 65280 up, but
font B fills it.

## The formats

### The landscape

- **The map** (57310): one column id a byte. Screen k (0-60) is
  57310+32k to 57310+32k+31. The 64 bytes from 59262 repeat the first 64,
  so that the view can run past the end before the pointer wraps
  (graphics.md).
- **Columns** (60430): id c (1-255) at 60430 + 14(c-1): for character
  rows 16 to 22, a byte of ink (1-7) and a character code (32-127). Ids
  below 216 use font A, 216 and up font B. 248 ids appear in the map;
  id 0 would stop the program (57130 jumps to the ROM's report 9).
- **The keys' positions** are variables (41211, a map address per key),
  not map data.

### The underground

- **Rooms** (47790): room n (0-63) at 47790 + 40n: 5 rows of 8 block
  types, 0 for none.
- **Block types** (45980): type t (1-74) at 45980 + 24t: 4 rows of
  `inks, char1, char2, inks, char3, char4`. char1's ink is `inks >> 4`
  and char2's `inks AND 7` (45847); both are drawn BRIGHT on black.
  Character 32 leaves the cell alone. Glyph c is at 59074 + 8c.
- **Room records** (42501): room n at 42501 + 17n, 17 bytes read by the
  compiled code (what is in the room); the game writes to some of them
  as it goes (42501, 42569, 42705, ...).
- **Entry positions** (45320): room n at 45320 + 2n, the witch's x and
  y on arriving from outside.
- **Exits** (45448): room n at 45448 + 4n, four room numbers; 255 for
  none, 128 and above for a way out.
- **Door to room** (41071, a variable array): the room each outdoor door
  leads to. In play it holds 18, 51, 48, 4, 6 and 14 for doors 2 to 7.

The decompiler's research (compiler.md) has the meaning of the record
fields and the exits' order; this file has their extent.

### Sprites

A graphic is rows x width bytes, row by row, MSB leftmost, no mask
(runtime.md, SPRITE). The frames of a set follow each other. The sets:

| First frame | Rows x bytes | Frames | What |
|---|---|---|---|
| 42450 | 8 x 3 | 2 | Shots |
| 43590 | 24 x 3 | 4 | Skeleton |
| 43878 | 24 x 3 | 20 | Frogs (4), the ingredients and objects, bones (4), skulls (4); 45174 and 45246 are set in two sprite blocks at start |
| 50800 | 24 x 3 | 4 | The witch on foot |
| 51090 | 24 x 3 | 8 | The witch on foot (two bytes after the set above) |
| 52948 | 16 x 2 | 4 | |
| 53076 | 16 x 2 | 4 | (*not seen read*) |
| 53204 | 16 x 2 | 4 | |
| 53340 | 24 x 2 | 4 | (*not seen read*) |
| 53532 | 24 x 2 | 4 | Vertical bars, drawn in the witch's block |
| 53730 | 16 x 3 | 4 | Bats |
| 53922 | 16 x 3 | 4 | (*not seen read*) |
| 54120 | 24 x 3 | 8 | The witch flying |
| 54696 | 24 x 3 | 4 | Ghost |
| 54984 | 24 x 3 | 4 | Explosion |
| 55272 | 24 x 3 | 4 | Pumpkin (*not seen read*) |
| 60100 | 24 x 2 | 5 | |

The *not seen read* sets' geometry is inferred: their neighbours' sizes,
how they look drawn at that width, and the object types table, which
names 53340 as 24 x 2 bytes.

**Object types** (42282): 21 entries of 8 bytes: the first frame's
address (word), rows, width in bytes, ink (the attribute SPRITE's mode 0
gives underground), the number of frames (4 or 1), and two more
parameters. Their graphics: 53730, 43590, 55272, 43878, 54696, 44742,
44454, 53204, 44166, 42450, 42474, 45246, 45174, 45030, 53730, 43590,
53204, 44166, 43878, 45102, 53340.

### Text

PRINT strings with control codes (16 INK, 19 BRIGHT, 22 AT) for the
panel font, whose O glyph is a zero:

| Address | Bytes | Text |
|---|---|---|
| 42169 | 111 | The ending: WELL DONE, THOU HAST COMPLETED CAULDRON WITH A SCORE OF, THE PUMPKIN IS DEAD, LONG LIVE THE PUMPKIN |
| 50388 | 162 | Game over: THY QUEST HAS FAILED, DO NOT DISMAY, ... THY SCORE IS |
| 50550 | 212 | The menu |
| 55641 | 82 | The panel's two scrolls |
| 55723 | 254 | The cottage: six scrolls and the cauldron |
| 55977 | 47 | The panel's labels |
| 56024 | 73 | The moon and six stars |

### The variables

41015-41570 are the compiled program's integer variables and arrays, a
word each, all zero on the tape and set by the program's start. Their
names and meanings are the decompiler's (tools/decompile_names.py);
the POK file's addresses fall in this block (lives 41315, magic 41313,
the keys 41239-41245, the items 41017-41027).

## Free space in the original

The unused regions above add up to little: the largest are 41732-42139
(408 bytes) and 57254-57309. The original fills its 40K; a port's budget
should start from the regions' sizes in the table, not from free space.
