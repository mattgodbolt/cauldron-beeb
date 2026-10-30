# The game logic: an outline

A first map of Cauldron's compiled BASIC, from the decompiled listing
(`make bas` writes `build/cauldron.bas`; [compiler.md](compiler.md) explains
the code it comes from, [runtime.md](runtime.md) the machine code it calls,
[data.md](data.md) the data it reads and [graphics.md](graphics.md) the
drawing). It is an index to split the logic by: each part
names its subroutines and the address ranges they cover. The names are the
listing's, from `tools/decompile_names.py`; where one is a guess it says so
here, and later reading should correct the table there.

Addresses are the original's. In the listing, `GOSUB 27996 [walk_step]`
gives the address and the name; `x`, `q`, `m` and the other single letters
are the source's own FOR variables.

## Conventions

- **Coordinates** are BASIC's: x is 0-255 from the left, y is 0-175 from
  the bottom, and a sprite's y is its top row. The hag stands on the ground
  at `hag_y = 23` and flies between 23 and 159; her x runs 0-232.
- **The stick**: `read_stick` (29505) calls USR 51900 with the control
  method in PRBUFF (0 Kempston, 1 Sinclair, 2 keys) and leaves `stick` = 0
  for none or 1-8 clockwise from up (1 up, 2 up-right, 3 right ... 7 left, 8
  up-left), and `fire`. The keys are CAPS SHIFT left, Z right, C up, X down,
  V fire. `stick_up` (31767), `stick_down` (31826), `stick_right` (31867)
  and `stick_left` (31908) set `flag` when the stick has that component.
- **`flag`** (41381) is the result of small tests: `flag_off` (31949)
  clears it and `flag_on` (31956) sets it.
- **Sprites** 0-7 are the blocks at 24759 (compiler.md). Their use: 0 and
  7 the chest and bag icons (and 0 the cauldron room's ingredients), 1 the
  hag (and the door's frames), 2 the hag's old image (erasing), 3 and 4 the
  spell (new and old) above ground and room things below, 5 and 6 monsters
  (new and old) and the chimney smoke.
- **Drawing is XOR**: everything is erased by drawing it again at its old
  place with its old graphic, so each mover keeps `old` copies of x, y and
  graphic.
- **Colour** is set by INK statements and by sprite modes (compiler.md).
  `ATTR_P`/`ATTR_T` are POKEd directly in places (27720, 37312, 39840).

## Start-up and a new game: 25592-26690

| Address | What |
|---|---|
| 25592 | `LET control = 2` (keys). Only the completion path returns here. |
| 25598 | A new game. RANDOMIZE; clear `ingr(1..6)`; `ingr(7..19)` = the records of the 13 rooms listed at 56920, each with its first thing cleared; by RND, one of the rooms of entries 7-11 gets the chest (kind 12) and one of 12-19 the bag (13). |
| 25879-26110 | The game's variables: score, magic 99, lives 8, `scroll = 58462` (the house), and the rest. |
| 26116-26340 | Clear the monster slots and keys 2-5; the door animation frames. |
| 26372-26480 | `door_room(2..6)`, `door_at(1..6)` (the doors' scroll positions; 1 is the house) and `key_spots(1..7)`. |
| 26486-26653 | Place keys 2-5 at four different `key_spots`, by RND 7. |
| 26685 | `reset_hag` (31988), then GOTO 30454. |

## Front end: 30454-30486, 39828-40050

30454 sets the colours, BORDER 0, CLS, and calls `menu` (39828):
`menu_text` (USR 50369) draws the menu; a flashing cursor marks the control
method; keys 1-3 choose it (with a BEEP) and 4, 0 or Kempston fire start.
Then `house_scene` (26691).

## The house and the cauldron: 26691-27153, 40581-40976, 39541-39827

| Address | What |
|---|---|
| 26691 `house_scene` | The cauldron room: `draw_house` (USR 55567), `draw_ingredients` (40581), the hag walks in (21 steps right), stirs (20 frames alternating two graphics), walks out (21 steps left), and `outdoors`. Reached at the start of each game and through door 1 (32769). |
| 40581 `draw_ingredients` | For each `ingr(s)` held, draw it in the cauldron at the position table at `mc_data + 2s`; then `items_got += items_now`, `items_now = 0`. |
| 27016 `outdoors` | CLS, `draw_land` (USR 55565), the house's door (`draw_door`), then the door opens (`open_door`), the hag walks out 30 steps and it closes (`close_door`). Also the way back from below ground (32863). |
| 29688 `open_door`, 29771 `close_door` | Three frames of the door (`door_frame` 29860 with `door_sprite_set`, `door_frame_gfx`, `draw_door_frame`), each with a `move_monsters` pass. |
| 39541 `smoke` | The chimney smoke over the house, 5 frames, called each pass while `scroll` is within 20 of the house. `erase_smoke` 39724. |

## The main loop: 30489-30748

One pass per move:

1. `hag_pass` (27154): read the stick, move and draw the hag (below).
2. If `crashed` and `hag_y <= 71`: `tumble` (33536), `respawn` (40096),
   `lose_life` (40051); game over goes to 40156.
3. On the ground (`hag_y = 23`), moving left with `x < 80`: `enter_door`
   (32569); then, with `x <= 9`, `take_key` (30089).
4. Every 7 passes, `spawn_monster` (33739). Then `move_monsters` (34517).
5. `magic <= 0` sets `crashed`.
6. `off_edge`: `scroll_screen` (28731).
7. Near the house, `smoke`.
8. `finished`: the completion at 40977.

## The hag above ground: 27154-28094, 30751-31291, 31687-31962

| Address | What |
|---|---|
| 27154 `hag_pass` | Flight speeds (`fly_speed`, m = 6), `read_stick`; if `crashed`, the stick is forced down and fire off. Falls into `move_hag`. |
| 27198 `move_hag` | On the ground (`hag_y = 23`) go to 27842. Otherwise: fire casts a spell; move the spell; animate; up (`hag_up`, to 143), down, right, left from the stick; choose the graphics; the tree test; off an edge sets `off_edge`. Then `draw_hag`. Also used by the scripted moves (`tumble`, `enter_door`). |
| 27424-27570 | **Hitting trees**: below y 71, where the ground's attributes at (21, 28) and (21, 4) aren't 65, a set pixel beside the hag's feet (POINT at `hag_oldx - 1` or `+ 24`, `hag_oldy - 18`) sets `crashed`. |
| 27620-27705 | On the ground: `idle` counts passes without input; after two the hag isn't redrawn (`delay`). |
| 27706 `draw_hag` | Erase the old image (`old_hag_sprite`, `erase_old_hag`), `restore_attrs` if needed, draw at (x, `hag_y`) in `hag_mode`, `moon`, keep the old position. |
| 27842-27995 | **Landing**: reaching y 23 with a flying graphic (`hag_gfx > 51675`) is a crash unless the screen bytes under the hag (`PEEK (x/8 + 20672)` or the next) are 170, the grass pattern: then `on_clearing`, and `clearing_x` is where the next life starts. Then walking. |
| 27996 `walk_step` | One step on the ground: `walk_right` (34422) or `walk_left` (34448), `walk_gfx_step` (28089), then 27620. |
| 30751 `hag_colours` | INK `hag_ink`, PAPER 0, BRIGHT 1. |
| 30817 `flying_gfx`, 30848 `set_hag_gfx`, 30872 `walking_gfx` | `hag_gfx = hag_gfx_base + 72 * anim`; the bases are 54408 and 54120 flying right and left, 51378 and 51090 walking. |
| 31711-31766 | `hag_up` (`hag_y += m`), `hag_right`, `hag_left` (by `hag_speed`, setting `facing`). |
| 31988 `reset_hag` | Not tumbling or crashed, flying graphics. |

## The spell: 28095-28730

`cast_spell` (28589) costs a point of magic and starts the spell beside the
hag, moving 12 a pass in the direction she faces, and up or down with the
stick. `spell_frame_step` (28095) animates it, `move_spell` (28129) moves
and draws it (sprites 3 and 4, mode 2) and ends it at the screen's edges or
after 14 passes; `erase_spell` (28469) erases the old image. A spell that
hits a monster: 34769.

## Scrolling and the landscape: 28731-29357, 29908-30088, 31292-31414

The landscape is a ring of columns: `scroll` is an address in the column
table, running from 57309 to 59293 and wrapping (29054-29131); the screen
shows the 32 columns from `scroll + 1`. `scroll_screen` (28731)
runs when the hag leaves the screen: it erases her, clears the monsters
(`clear_monsters` 29425), and shifts 32 columns, each by three USRs into
`mc_data` (56900 + 142 or 166, + 192 or 211, + 230) with the new column's
type in PRBUFF; a key lying in a new column is shown (`show_key`, 29358).
`save_attrs` (USR 51675) keeps the ground's attributes.

`find_door` (29908) looks for a door within 40 of `scroll` (`door_at`); a
door sets `door_prbuff` (31292) and `draw_door` (31379, USR `mc_data +
328`) draws it.

## Keys and doors: 29358-29507, 30089-30453, 32569-32866

| Address | What |
|---|---|
| 30089 `take_key` | At the left edge on the ground, within 50 of a key's place (`key_at`), take it (`keys(q) = 1`); the red key also opens door 6. Redraw (`draw_inventory`). |
| 30287 `draw_inventory` | The chest and bag (`draw_chest_bag` 40290, sprites 0 and 7 on the top corners) and the keys held (`print_key` 30401, in the key's INK). |
| 32569 `enter_door` | With a door here and its key held: open the door, walk the hag in, close it. Door 1 (the house) goes to `house_scene`; the others to `underground` (35524), then back out: redraw the monsters, CLS, `outdoors`. |

## Monsters above ground: 32922-35523

The four slots are the `m_*` arrays; `load_slot` (32922) copies slot `m`
into the `o_*` scalars and `store_slot` (33211) back. Above ground:

| Field | Meaning |
|---|---|
| `o_base` | the graphic base; 0: the slot is free |
| `o_x`, `o_y` | position; `o_dy` ±4 bounces it between y 71 and 135 |
| `o_ink` | its colour |
| `o_frame`, `o_stride` | animation: `o_gfx = o_base + o_stride * o_frame` |
| `o_rows`, `o_width` | size |
| `o_age`, `o_life` | it homes in on the hag once `o_age > o_life` (35394) |
| `o_dying` | counts up after a hit; the slot is freed at 5 |
| `o_drawn`, `o_oldx`, `o_oldy` | the old image, for erasing |

| Address | What |
|---|---|
| 33739 `spawn_monster` | In a free slot: scan 28 bytes of the screen from 20672 (from alternate ends, `spawn_side`), skipping each at random (RND 2), and start a monster over the first of five byte patterns found (127, 191, 119, 253, 239: six kinds, 119 having two by an earlier RND 2) (33966-34185). `monster_life` (34344): `o_life = RND 60`, or 20000 for the kind from 253. |
| 34517 `move_monsters` | For each slot: age, animate, move, home in, bounce; **the hag hit** (within 16 in x and y): magic - 4, score + 10, `sound_up`; **the spell hit**: score + 20, end the spell, `sound_down`. Either turns the monster into a dying animation (32365: `o_base = 54984`, `o_dying = 1`), freed after 5 passes. Off the screen: free the slot. Draw with sprites 5 and 6. |
| 31963 `kill_monster` | `erase_monster` (35270) and `clear_slot` (40134). |

## Below ground: 35524-39540

`underground` (35524) sets up the room behind the door (`room =
door_room(door)`), clears the screen, draws the cave (USR `mc_draw + 4`),
and runs its own loop at 35688-36486, until the hag leaves (36882) or dies
(36456).

| Address | What |
|---|---|
| 35597-35685 | A new life below ground: the hag's start in the room from the table at 45320 + 2 * room; `enter_room`. |
| 35688-36453 | One pass: `read_stick`; jumping (`jump`, `jump_t`, `jump_dy`, `jump_curve` 37238); `look_around` (36926) reads the attributes around the hag; standing and falling by attribute 5 (`stand_check` 37197) and 66, 68, 69; walking; leaving the room by an edge (36304-36383, 36590-36923): the neighbours come from the table at 45450 + 4 * room, 255 meaning none and a value over 63 the way out to the surface, taken from y 111 or higher (36824); `move_room_things`. |
| 37371 `enter_room` | Draw the room (USR 45710 `draw_room`), then load its four things from its record: 17 bytes at 42501 + 17 * room, a 4-byte entry per slot (kind, x, y, path). `load_kind` (37515) reads the kind's 8-byte record at 42274 + 8 * kind; paths are 6-byte entries at 41590. Things already taken are left out (37988-38198). |
| 38249 `move_room_things` | For each slot: follow its path (the step counts at 41590 + 6 * path, `o_life` stepping through them, each a direction: down, right, up, left, 4 pixels a step), animate, draw (sprites 3 and 4); touching the hag: kind 14 sets `finished`, 12 gives the chest, 13 the bag, 15-20 are ingredients (`take_ingredient` 39278); a harmful thing (`o_age = 0` here) costs magic (`lose_magic`, 31970), and in room 63 kills the hag unless all six ingredients are in the cauldron (`items_got = 6`). |
| 39278 `take_ingredient` | At most two at a time (`items_now`); the bones (16) need the chest and the fire (17) the bag; `ingr(kind - 14) = kind`, score + 1000. |

Below ground the slot fields change meaning: `o_type` is the kind,
`o_oldx`/`o_oldy` the position, `o_width` a path pointer, `o_steps` the
steps left, `o_life` the path index, `o_ink`/`o_x`/`o_y` the rows, width
and colour, `o_gfx`/`o_rows` the graphic and the old graphic, `o_dy` the
frame, `o_dying` the frame count, `o_age` 0 for harmful.

## Status: 30375-30453, 31415-31686, 32333-32511, 40203-40289

`update_status` (30375) redraws, when the hag is below y 143, `show_magic`
(31436: `PRINT AT 3,10; magic; "%"`), `show_lives` (31485: two rows of
broomsticks) and `show_score` (32333 via `print_score` 40203). `game_font`
(31415) points CHARS at the game's font first. `magic_floor` (32477) keeps
magic from going below 0.

## Losing a life, game over, completion: 33536-33738, 40051-40202, 40977-41014

| Address | What |
|---|---|
| 33536 `tumble` | Falling off the broom: the hag is driven up to y 135, then down to 36, then five more frames with the tumbling graphics, `sound_down` and a monster pass each step. |
| 40096 `respawn` | Back to flying height, or to the clearing she landed on (`on_clearing`, `clearing_x`). |
| 40051 `lose_life` | Lives - 1, magic 99; at 0 lives `game_over`. |
| 40156 | Game over: CLS, `game_over_text` (USR 50350), the score, `WAIT 300`, `wait_key`, then a new game at 25598. |
| 40977 | Completion: CLS, `end_text` (USR 42140), the score, `wait_key`, then 25592. |

## Sound

There is no sound routine of its own: `sound_down` (32194) and `sound_up`
(32265) sweep BEEPER (ROM 949) periods from 200 to 100 and 200 to 300 in
steps of 5, one cycle each; the menu's `BEEP 1/10, 0` is the only BEEP. The
hand-written machine code may make more; that hasn't been looked at.

## Machine code called by USR

| Address | What |
|---|---|
| 42140 `end_text` | the completion text, in the game font |
| 45710 `draw_room` | an underground room (PRBUFF = room) |
| 50350 `game_over_text`, 50369 `menu_text` | text screens through PR-STRING |
| 51675 `save_attrs`, 51687 `restore_attrs` | the attributes of rows 16-21, to and from 51700 |
| 51900 `read_stick` | the controls |
| 52852 `moon_attrs` | the moon's attributes |
| 55565 (`mc_draw`), + 2, + 4 | the landscape, the house's inside, the cave |
| 56900 (`mc_data`) + 142, 166, 192, 211, 230, 328 | the column scroll and the door |

## Data the logic reads

[data.md](data.md) has the formats.

| Address | What |
|---|---|
| 20672 on | screen memory (character row 22): the grass test and the monster spawn scan read it |
| 41590 | movement paths, 6 bytes each |
| 42274 | the kinds of thing below ground, 8 bytes each |
| 42501 | the room records, 17 bytes each |
| 45320, 45450 | per room: the hag's start (2 bytes) and the neighbours (4 bytes) |
| 56920 | the 13 rooms that can hold the chest and bag |
| 57309 on | the landscape's columns (a byte each) |

## Not yet understood

- `v41295` is read at 34966 but never set to anything but 0: a dead branch.
- `v41327`, `v41339`, `v41341`, `v41317`, `v41361` are set and never read.
- The kinds of monster above ground (33966-34185) and below ground (the
  records at 42274) haven't been matched to their graphics.
- Which ingredient each kind 15-20 is comes from the POKEs (15 bat, 16
  bones, 17 fire, 18 plant, 19 frog, 20 lizard), not from the code.

## Splitting the work

The parts above share only the variables and a few subroutines
(`load_slot`/`store_slot`, the sprites, `flag`). A split that keeps each
agent's subroutines together:

1. **Core and front end**: start-up and a new game, the menu, the house
   and cauldron, status, losing a life, game over, completion, sound.
2. **The hag above ground**: `hag_pass`, `move_hag`, landing and trees,
   walking, the spell, `tumble`, `respawn`.
3. **The landscape**: scrolling, doors and keys, with the machine code
   behind `mc_draw` and `mc_data`.
4. **Monsters above ground**: `spawn_monster`, `move_monsters` and the
   slot routines.
5. **Below ground**: `underground`, `enter_room`, `move_room_things`,
   `take_ingredient`, with `draw_room` (USR 45710) and the room data.
