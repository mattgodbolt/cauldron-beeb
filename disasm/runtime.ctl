; Cauldron (ZX Spectrum): the compiler's runtime library, the hand-written
; machine code and the data regions. The compiled BASIC itself
; (25592-41012) and the variables' names belong to the decompiler's
; research (docs/research/compiler.md); docs/research/runtime.md,
; graphics.md and data.md describe what is here.
;
; Addresses are decimal, as the docs cite them.

@ 24600 start
@ 24600 org
c 24600 Entry: the TAP's BASIC calls here
@ 24600 label=ENTRY
D 24600 The game starts at the compiled program's first statement.

; ---------------------------------------------------------------------------
; The compiler's workspace
; ---------------------------------------------------------------------------

b 24603 Compiler workspace
@ 24603 label=WORKSPACE
D 24603 FOR-NEXT control blocks (limit, step and loop-back address, a word each) that the compiled FOR statements write and their NEXTs read, at fixed addresses per loop. Zero on the tape.
B 24603,156,12

b 24759 Sprite parameter blocks
@ 24759 label=SPRITES
D 24759 Eight blocks of 8 bytes, block n at 24759+8n, each passed to SPRITE (25431) in HL: graphic address (word), x (0-255), y (PLOT coordinates: 175 is the top pixel row), rows, width in bytes, attribute mode, attribute. The compiled code fills them before each call; zero on the tape.
B 24759,64,8

; ---------------------------------------------------------------------------
; The runtime library
; ---------------------------------------------------------------------------

c 24823 DRAW: draw a line
@ 24823 label=RT_DRAW
D 24823 HL=dx, DE=dy (signed). Splits them into magnitude and sign and calls the ROM's DRAW-LINE (9402), keeping H'L'.
c 24860 Recolour the whole attribute file
@ 24860 label=RT_ATTRMASK
D 24860 B=bits to set, C=bits to replace: each of the 768 attributes becomes (attr AND NOT C) OR B.
c 24880 Multiply
@ 24880 label=RT_MUL
D 24880 HL=HL*DE (signed, 16-bit result) by shift and add, signs handled by RT_SIGNS.
c 24911 Divide
@ 24911 label=RT_DIV
D 24911 HL=HL/DE (signed), DE=remainder. A divisor of 0 returns 0.
c 24972 Negate
@ 24972 label=RT_NEG
D 24972 HL=-HL.
c 24980 Compare: equal
@ 24980 label=RT_EQ
D 24980 HL=1 if HL=DE, else 0 (flags from SBC HL,DE). The compiler's true is 1.
c 24989 Compare: not equal
@ 24989 label=RT_NE
c 24998 Compare: greater or equal
@ 24998 label=RT_GE
D 24998 HL=1 if HL>=DE (signed). 24999 is HL<=DE.
@ 24999 label=RT_LE
c 25008 Compare: less than
@ 25008 label=RT_LT
D 25008 HL=1 if HL<DE (signed: the sign of HL-DE corrected for overflow).
c 25023 Compare: greater than
@ 25023 label=RT_GT
c 25026 INKEY$
@ 25026 label=RT_INKEY
D 25026 ROM KEY-SCAN, K-TEST, K-DECODE: HL=the key's code, or 0.
c 25048 PEEK
@ 25048 label=RT_PEEK
@ 25045 label=RT_RET_L
c 25051 IN
@ 25051 label=RT_IN
c 25057 Make both operands positive
@ 25057 label=RT_SIGNS
D 25057 For MUL and DIV: negates negative HL and DE, A counting how many were.
@ 25063 label=RT_ABS
c 25073 POINT
@ 25073 label=RT_POINT
D 25073 L=x, E=y: ROM PIXEL-ADD (8874), HL=the pixel (0 or 1).
c 25089 ATTR
@ 25089 label=RT_ATTR
D 25089 L=line, E=column: HL=the attribute byte.
c 25106 SCREEN$
@ 25106 label=RT_SCREEN
D 25106 Matches the cell (L=line, E=column) against the 96 glyphs at CHARS+256, plain or inverse. HL=the code, or 0.
c 25173 AND (bitwise)
@ 25173 label=RT_AND
c 25180 OR (bitwise)
@ 25180 label=RT_OR
c 25187 NOT
@ 25187 label=RT_NOT
D 25187 HL=1 if HL=0, else 0.
c 25195 SGN
@ 25195 label=RT_SGN
c 25205 USR
@ 25205 label=RT_USR
D 25205 Calls HL; returns BC in HL, as USR does.
c 25212 Empty statement
@ 25212 label=RT_NOP
c 25213 RET
c 25214 RND
@ 25214 label=RT_RND
D 25214 seed=(seed+1)*77 (78 if that is 0) less 1, by the signed multiply, kept in DEFADD (23563), which start-up seeds from FRAMES (25598). HL=the new seed modulo the argument, by the signed divide.
w 25244 Powers of ten for PRINT
@ 25244 label=RT_TENS
c 25252 PRINT a number
@ 25252 label=RT_PRINTNUM
D 25252 Prints HL as a signed decimal through RST 16, without leading zeros.
c 25310 INPUT a number
@ 25310 label=RT_INPUT
D 25310 Runs the ROM's editor (3884) with ERR-SP pointed at a recovery, then evaluates the line. BC=the number, 0 on an error. Not reached in play.
c 25380 Trace: print the line number, check BREAK
@ 25380 label=RT_TRACE
D 25380 Prints [line] at row 0, column 25 of the lower screen, then stops with report L if BREAK is pressed. Not reached in play.
c 25416 BEEP
@ 25416 label=RT_BEEP
D 25416 Stacks HL (the pitch) as a small integer on the calculator stack, above the duration the compiled code stacked, and calls the ROM's BEEP (1016).

c 25431 SPRITE: draw or erase a sprite
@ 25431 label=SPRITE
D 25431 HL=a parameter block (24759+8n): the graphic's address (word), x, y (PLOT coordinates), rows, width in bytes, attribute mode, attribute.
D 25431 For each pixel row, from y downwards: ROM PIXEL-ADD (8874) finds the screen byte; for each of the row's cells (width, plus one when x is not a multiple of 8) the attribute is set by the mode: 0 sets it to the block's attribute if it equals ATTR-P (23693); 1 sets it back to ATTR-P if it equals the block's attribute; 2 applies the ROM's print colours (ATTR-T and MASK-T, P-FLAG) through PO-ATTR (3044). Then the row's bytes are XORed onto the screen, shifted right by x mod 8 into width+1 bytes. No mask, no clipping: a y below 0 or above 175 stops the program (PIXEL-ADD's report B).
@ 25444 label=SPR_ROW
@ 25462 label=SPR_ATTRS
@ 25518 label=SPR_SHIFTED
@ 25545 label=SPR_ALIGNED
c 25563 Set up IM 2 (not used)
@ 25563 label=RT_IM2
D 25563 Points the vector at 65279 to 25576 and selects IM 2. The game never calls it; it runs in IM 1.
c 25576 IM 2 handler (not used)
@ 25576 label=RT_IM2_INT
D 25576 Calls the address patched into 25583, then joins the ROM's IM 1 handler at 58.

c 25592 Compiled BASIC
@ 25592 label=BASIC
D 25592 The game's logic, compiled. See docs/research/compiler.md and the decompiler.

; ---------------------------------------------------------------------------
; The variables and the data above the compiled code
; ---------------------------------------------------------------------------

b 41015 The compiled program's variables
@ 41015 label=VARS
D 41015 Integer variables and arrays, a word each (to 41570); their names and meanings are in the decompiler's research. Zero on the tape: start-up sets them.
B 41015,556,16
s 41571 Unused
b 41575 String literals for PRINT
@ 41575 label=STRINGS
D 41575 Printed with PR-STRING by the compiled code: the key's two glyphs (41575), the magic digits (41579) and blanks.
B 41575,15,8
b 41590 Small tables read with PEEK
@ 41590 label=PEEK_TABLES
B 41590,142,8
s 41732 Unused
c 42140 Print the ending text
@ 42140 label=PRINT_ENDING
D 42140 Prints the text at 42169 with the panel font (CHARS 55874), restoring CHARS after.
t 42169 The ending text
@ 42169 label=ENDING_TEXT
D 42169 PRINT control codes (16 INK, 22 AT) and text; the font draws a zero for O.
B 42169,5
T 42174,9
B 42183,3
T 42186,19
B 42205,3
T 42208,15
B 42223,3
T 42226,8
B 42234,3
T 42237,19
B 42256,3
T 42259,21
s 42280 Unused
b 42282 Object types
@ 42282 label=OBJECT_TYPES
D 42282 21 types, 8 bytes each: the graphic's first frame (word), rows, width in bytes, ink, frames, two more parameters. Read with PEEK.
B 42282,168,8
b 42450 Sprite graphics: shots (8 rows x 3 bytes)
@ 42450 label=GFX_SHOT
B 42450,48,3
s 42498 Unused
b 42501 Room records
@ 42501 label=ROOM_RECORDS
D 42501 64 rooms of 17 bytes (room n at 42501+17n), read with PEEK and partly written as the game goes.
B 42501,1088,17
b 43589 Sprite graphics (24 rows x 3 bytes a frame)
@ 43589 label=GFX_SKELETON
D 43589 A skeleton (43590, 4 frames), then 20 frames from 43878: frogs, ingredients, bones, skulls and more (docs/research/data.md).
B 43589,1,1
B 43590,1728,3
s 45318 Unused
b 45320 Room entry positions
@ 45320 label=ROOM_ENTRY
D 45320 64 rooms x (x, y): where the witch appears on entering a room from outside.
B 45320,128,2
b 45448 Room exits
@ 45448 label=ROOM_EXITS
D 45448 64 rooms x 4 room numbers; 255 is no exit, 128 and up lead outside.
B 45448,256,4
s 45704 Unused

c 45710 Draw an underground room
@ 45710 label=DRAW_ROOM
D 45710 (23296)=the room (0-63), (23297)=the attribute for its empty cells. Clears character rows 4-23 (rows 4-7 by printing glyph 32), sets their attributes, then draws the room's 5 x 8 blocks of 4 x 4 characters from ROOMS (47790), straight to the screen with the underground font.
@ 45810 label=DRAW_BLOCK
@ 45834 label=BLOCK_ADDR
@ 45847 label=BLOCK_PAIR
@ 45870 label=BLOCK_CHAR
@ 45892 label=SKIP_CELL
@ 45900 label=CELL_ADDR
@ 45926 label=PUT_CHAR
w 45970 The underground font's base
@ 45970 label=UNDER_CHARS
D 45970 Glyph c is at (45970) + 8c: 59074.
w 45972 The next screen address
@ 45972 label=PUT_POS
b 45974 Unused bytes
b 45980 Underground block types
@ 45980 label=BLOCKS
D 45980 75 block types of 24 bytes (type t at 45980+24t; type 0 is never drawn): 4 rows x 2 x (inks, char, char). The first char's ink is the high nibble, the second's bits 0-2; both are drawn BRIGHT on black. Char 32 leaves the cell as it was.
B 45980,1800,6
s 47780 Unused
b 47790 Underground rooms
@ 47790 label=ROOMS
D 47790 64 rooms of 40 bytes (room n at 47790+40n): 5 rows x 8 block types, 0 for none. Block row r covers character rows 3+4r to 6+4r; no block draws anything in its top row when it is in the room's top row.
B 47790,2560,8

c 50350 Print the game-over text
@ 50350 label=PRINT_GAME_OVER
D 50350 Prints the text at 50388 with the panel font. 50340-50349 are not code.
c 50369 Print the menu
@ 50369 label=PRINT_MENU
D 50369 Prints the menu at 50550 with the panel font, on stream 2, and puts CHARS back.
t 50388 Game-over text
@ 50388 label=GAME_OVER_TEXT
B 50388,162,8
t 50550 Menu text
@ 50550 label=MENU_TEXT
B 50550,212,8
c 50762 Open stream 2
@ 50762 label=OPEN_SCREEN
c 50768 Select the panel font
@ 50768 label=PANEL_FONT
c 50775 Select the ROM font
@ 50775 label=ROM_FONT
b 50782 Unused bytes
b 50800 Sprite graphics: the witch on foot (24 rows x 3 bytes a frame)
@ 50800 label=GFX_WITCH_WALK
D 50800 4 frames from 50800, then 8 from 51090.
B 50800,288,3
B 51088,2,2
B 51090,576,3
s 51666 Unused
c 51675 Save the landscape's attributes
@ 51675 label=SAVE_LAND_ATTRS
D 51675 Copies the 192 attributes of character rows 16-21 to 51700.
c 51687 Restore the landscape's attributes
@ 51687 label=RESTORE_LAND_ATTRS
D 51687 Copies them back: run every pass outdoors, it undoes the colour the sprites left on the landscape.
b 51699 Unused
b 51700 The landscape's saved attributes
@ 51700 label=LAND_ATTRS
B 51700,192,32
s 51892 Unused
c 51900 Read the controls
@ 51900 label=READ_CONTROLS
D 51900 (23296)=the control method (0 Kempston, 1 Sinclair 2, 2 keys CAPS SHIFT to V). Leaves the direction in 23728 (0 none, 1 up, then clockwise to 8 up-left) and fire in 23729 (1 when pressed).
@ 51926 label=READ_KEMPSTON
@ 51991 label=READ_KEYS
@ 52088 label=READ_SINCLAIR
@ 52239 label=SET_DIRECTION
@ 52284 label=SET_FIRE
s 52294 Unused
b 52300 Door graphic (32 rows x 4 bytes, 4 frames)
@ 52300 label=GFX_DOOR
D 52300 Not seen drawn in play.
B 52300,512,4
s 52812 Unused
b 52820 The moon's attributes
@ 52820 label=MOON_ATTRS
D 52820 5 rows x 6, copied to rows 7-11, columns 6-11 by 52852.
B 52820,30,6
s 52850 Unused
c 52852 Restore the moon's attributes
@ 52852 label=RESTORE_MOON_ATTRS
s 52878 Unused
b 52896 Small graphic (keys?)
B 52896,52,2
b 52948 Sprite graphics (16 rows x 2 bytes a frame)
@ 52948 label=GFX_16x2
D 52948 Twelve frames: 52948 (4), 53076 (4, not seen drawn), 53204 (4).
B 52948,384,2
b 53332 Unused bytes
b 53340 Sprite graphics (24 rows x 2 bytes, 4 frames; not seen drawn)
@ 53340 label=GFX_53340
B 53340,192,2
b 53532 Sprite graphics (24 rows x 2 bytes, 4 frames)
@ 53532 label=GFX_53532
B 53532,192,2
s 53724 Unused
b 53730 Sprite graphics: bats (16 rows x 3 bytes, 4 frames; 4 more at 53922)
@ 53730 label=GFX_BAT
B 53730,384,3
s 54114 Unused
b 54120 Sprite graphics: the witch flying (24 rows x 3 bytes, 8 frames)
@ 54120 label=GFX_WITCH_FLY
B 54120,576,3
b 54696 Sprite graphics: ghost, explosion, pumpkins (24 rows x 3 bytes, 4 frames each)
@ 54696 label=GFX_GHOST
@ 54984 label=GFX_54984
@ 55272 label=GFX_PUMPKIN
B 54696,864,3
s 55560 Unused
c 55565 Print the outdoor scenery and the panel
@ 55565 label=PRINT_OUTDOORS
D 55565 Three entries, each opening stream 2 with the panel font (CHARS 55874) and ending with the panel (55574): 55565 prints the moon and stars (56024) first, 55567 the cottage's scrolls (55723), and 55569 the panel alone. The panel is its scrolls (55641) and labels (55977). CHARS goes back to the ROM's at the end.
@ 55567 label=PRINT_COTTAGE
@ 55569 label=PRINT_PANEL_ONLY
@ 55574 label=PRINT_PANEL
@ 55622 label=SCENERY_FONT
t 55641 Panel and scenery strings
@ 55641 label=SCENERY_TEXT
D 55641 PRINT strings for the panel font: the panel's scrolls (55641, 82 bytes), the cottage's scrolls (55723, 254), the panel's labels (55977, 47) and the moon and stars (56024, 73).
B 55641,456,8
s 56097 Unused
b 56130 The panel font
@ 56130 label=PANEL_FONT_DATA
D 56130 CHARS=55874: codes 32-127. The digits, capitals (the texts spell O as a zero) and the scroll, moon and star pieces.
B 56130,768,8
b 56898 Unused bytes, and a list read with PEEK (56920)
B 56898,35,8
c 56933 Remains of a 1-pixel scroll (not used)
c 56964 Scroll the landscape left 4 pixels (not used)
@ 56964 label=SCROLL4_LEFT
D 56964 RLD across the bottom third. 56900 (the base the compiled code keeps in a variable) + 64; the game uses the 8-pixel routines at +142 and +166.
c 57005 Scroll the landscape right 4 pixels (not used)
@ 57005 label=SCROLL4_RIGHT
c 57042 Scroll the landscape left a character
@ 57042 label=SCROLL_LEFT
D 57042 Moves each byte of the bottom third (character rows 16-23) one column left, column by column, 31 columns x 64 pixel rows.
c 57066 Scroll the landscape right a character
@ 57066 label=SCROLL_RIGHT
c 57092 Scroll the landscape's attributes left
@ 57092 label=SCROLL_ATTRS_LEFT
D 57092 Rows 16-23.
c 57111 Scroll the landscape's attributes right
@ 57111 label=SCROLL_ATTRS_RIGHT
c 57130 Print a landscape column
@ 57130 label=PRINT_COLUMN
D 57130 (23296)=the column id (1-255; 0 stops the program with report 9), (23297)=the screen column. Prints the column's 7 cells at rows 16-22 through RST 16 (INK, AT, char), with CHARS 63744 for ids below 216 and 64512 from 216, and DF-SZ 0 so row 22 can be printed.
@ 57203 label=PRINT_CELLS
c 57228 Print the whole landscape
@ 57228 label=PRINT_LANDSCAPE
D 57228 (23296)=the map address of the leftmost column (a word): prints 32 columns with PRINT_COLUMN.
s 57254 Unused
b 57310 The landscape map
@ 57310 label=LAND_MAP
D 57310 One column id a byte. 61 screens of 32 columns (1952), then the first 64 again so the view can wrap without a test.
B 57310,2016,32
s 59326 Unused
b 59330 The underground font
@ 59330 label=UNDER_FONT
D 59330 Codes 32-127, glyph c at 59074+8c.
B 59330,768,8
s 60098 Unused
b 60100 Sprite graphics (24 rows x 2 bytes, 5 frames)
@ 60100 label=GFX_60100
B 60100,240,2
b 60340 Unused column ids (not read in play)
B 60340,90,10
b 60430 Landscape columns
@ 60430 label=LAND_COLUMNS
D 60430 Column id c (1-255) at 60430+14(c-1): 7 x (ink, char) for character rows 16-22.
B 60430,3570,14
b 64000 Landscape font A
@ 64000 label=LAND_FONT_A
D 64000 CHARS=63744: codes 32-127, for column ids 1-215.
B 64000,768,8
b 64768 Landscape font B
@ 64768 label=LAND_FONT_B
D 64768 CHARS=64512: codes 32-127, for column ids 216-255. Its codes 107-127 are also where the ROM's UDGs would be (65368).
B 64768,768,8
i 65536
