"""Names for the compiled BASIC's variables, arrays and subroutines.

tools/decompile.py reads these tables to name what it prints. Add to them
as the logic is read: a name here should be backed by the POKEs, the
instructions, or a reading of the listing (say which in the comment).
Unnamed variables print as v<address>, arrays as a<address>(i), subroutines
as their address. docs/research/logic-outline.md explains the names.

Variables are 16-bit words. An array's element i (from 1) is the word at
base + 2*(i-1); ARRAYS names the base. A constant index is folded by the
compiler into a plain address, which the listing prints as an element of
the array it falls in.

A FOR loop's variable is a single letter in Sinclair BASIC, and the
compiler gives each letter its own slot (see compiler.md), so the letters
of the FOR variables are the source's own names; the decompiler names them
from their slots, and the entries below keep those letters. The program
reuses variables for unrelated jobs: x is a loop counter at start-up and
the hag's x after it; m is the monster slot being worked on and also the
hag's vertical step. The comments say so.
"""

# Word variables, by address.
VARS = {
    41015: "control",        # 0 Kempston, 1 Sinclair, 2 keys: 39975 (menu keys 1-3), passed to USR 51900 in PRBUFF
    41277: "x",              # FOR x at start-up; then the hag's x (pixels, 0..232)
    41279: "p",              # walks the table at 56920 at start-up
    41281: "items_now",      # ingredients found this trip below ground; added to items_got at 40898
    41283: "items_got",      # POK: items picked up (0-6)
    41285: "has_chest",      # set when a type-12 object is touched (38974); POK names 41286 "Chest"
    41287: "has_bag",        # set when a type-13 object is touched (39002); POK: "Bag"
    41289: "finished",       # POK: finish game; set by touching a type-14 object (38952)
    41291: "smoke_frame",    # 0..4, chimney smoke animation (39541)
    41293: "smoke_shown",    # the smoke sprite is drawn (needs erasing)
    41297: "off_edge",       # the hag left the screen: scroll (28731)
    41299: "m",              # FOR m: the monster slot 32922/33211 work on; also the hag's vertical step (31711)
    41301: "score_digits",   # digits of the score above the first (32410)
    41303: "score",
    41305: "spell_done",     # the spell (shot) has ended (28129)
    41307: "game_over",      # set when lives reach 0 (40090)
    41309: "spell_x",
    41311: "spell_y",
    41313: "magic",          # POK: magic (current life)
    41315: "lives",          # POK: lives
    41319: "mc_draw",        # 55565: base of the machine-code screen routines (USR mc_draw, +2, +4)
    41321: "mc_data",        # 56900: base of more machine code and tables (USR mc_data+230, +328)
    41323: "spawn_timer",    # counts main-loop passes; a monster is started every 7 (30643)
    41325: "hag_ink",        # the hag's colour
    41329: "scroll",         # the landscape position: an address in the map columns (57341..59261)
    41331: "hag_oldx",       # where the hag was drawn, for erasing
    41333: "walking",        # the hag is on the ground (above ground)
    41335: "facing",         # 1 right, -1 left
    41337: "scroll_usr1",    # USR addresses for the column scroll (28774)
    41343: "anim",           # 0..3 animation frame (30903)
    41347: "spawn_side",     # alternates the side a monster starts from (33840)
    41349: "spell_on",       # a spell is in flight
    41351: "q",              # FOR q: the commonest loop; also INKEY$ in the menu and a table pointer
    41353: "w",              # FOR w; also a random pick (26510)
    41355: "r",              # FOR r
    41357: "indoors",        # 1 in the house and below ground (the title too): no flight sound
    41363: "hag_mode",       # the sprite mode the hag is drawn with
    41365: "hag_y",          # the hag's y (BASIC pixels, sprite top: 23 on the ground)
    41367: "stick",          # direction read by USR 51900: 0 none, 1 up .. 8 up-left, clockwise
    41369: "hag_gfx",        # the hag's current graphic
    41371: "on_clearing",    # landed on a clearing (grass bytes 170 below)
    41375: "jump",           # below ground: 0 standing, 1 rising, 2 falling
    41377: "crashed",        # the hag hit something and falls (27570, 30671)
    41379: "fire",           # fire button, read by USR 51900
    41381: "flag",           # the result of the small test subroutines (31949 clears, 31956 sets)
    41383: "tumbling",       # falling off the broom (30538)
    41385: "hag_gfx_base",   # graphic set for the hag (flying right/left, walking)
    41387: "fall_gfx",       # graphic set while tumbling
    41389: "hag_oldy",
    41391: "idle",           # passes with no input on the ground
    41393: "hag_drawn",
    41395: "hag_erase",
    41397: "usr_result",     # LET usr_result = USR n: the result is never read
    41399: "hag_oldgfx",
    41403: "clearing_x",     # x of the clearing landed on: where a new life starts
    41405: "spell_frame",
    41407: "spell_age",
    41409: "spell_gfx",
    41411: "spell_dx",
    41413: "spell_dy",
    41455: "hag_speed",      # horizontal step
    41425: "f",              # FOR f: the scroll's 32 columns; a delay loop
    41437: "e",              # FOR e: door animation frame
    41463: "t",              # FOR t: the sound loops' BEEPER period
    41477: "d",              # FOR d
    41465: "pr_row",         # where 40203 prints the score
    41467: "pr_col",
    41431: "o_base",         # o_*: the slot being worked on (see m_*)
    41461: "o_y",
    41469: "o_drawn",
    41471: "o_frame",
    41473: "o_dying",
    41479: "o_type",
    41481: "o_steps",
    41483: "o_oldx",
    41485: "o_oldy",
    41487: "o_gfx",
    41489: "o_ink",
    41491: "o_x",
    41493: "o_age",
    41495: "o_dy",
    41497: "o_stride",
    41499: "o_rows",
    41501: "o_width",
    41503: "o_life",
    41519: "room",
    41569: "s",              # FOR s: the ingredient being drawn in the cauldron room           # the underground room (records of 17 bytes at 42501)
    41521: "dead",           # below ground: the hag dies (36423)
    41523: "jump_t",         # below ground: jump time
    41525: "jump_dy",
    41527: "attr_under",     # ATTR below the hag (36926)
}

# Arrays, by base address (element 1's address).
ARRAYS = {
    41017: "ingr",           # 1-6: POK ingredients (15 bat .. 20 lizard when held); 7-19: room-record addresses
    # The four monster slots: load_slot (32922) copies slot m's elements to
    # the o_* scalars and store_slot (33211) copies them back. Above ground
    # and below ground use them differently; the names are the above-ground
    # meaning, and logic-outline.md has both.
    41055: "m_type",
    41063: "m_steps",
    41083: "m_life",
    41091: "m_dying",
    41099: "m_ink",
    41107: "m_stride",
    41115: "m_drawn",
    41123: "m_width",
    41131: "m_rows",
    41139: "m_frame",
    41147: "m_x",
    41155: "m_y",
    41163: "m_base",         # the graphic base; 0: the slot is empty
    41171: "m_oldx",
    41179: "m_oldy",
    41187: "m_gfx",
    41195: "m_age",
    41203: "m_dy",
    41071: "door_room",      # 2-6: the underground room behind each door
    41211: "key_at",         # 2-5: where each key lies (a scroll position, from key_spots)
    41223: "key_spots",      # 1-7: the places a key can be
    41237: "keys",           # 1 the house, 2 red, 3 purple, 4 green, 5 cyan (POK), 6 follows red
    41249: "door_at",        # 1-6: the doors' scroll positions (1 is the house)
    41261: "door_gfx24",     # 1-4: door animation frames, 24 rows by 2 bytes (53532 + 48*k)
    41269: "door_gfx32",     # 1-4: door animation frames, 32 rows by 4 bytes (52300 + 128*k)
}

# Subroutines (GOSUB targets), by entry address.
SUBS = {
    26691: "house_scene",
    27016: "outdoors",
    27154: "hag_pass",
    27198: "move_hag",
    27706: "draw_hag",
    27750: "draw_hag_at",
    27996: "walk_step",
    28095: "spell_frame_step",
    28129: "move_spell",
    28469: "erase_spell",
    28589: "cast_spell",
    28731: "scroll_screen",
    29358: "show_key",
    29425: "clear_monsters",
    29505: "read_stick",
    29908: "find_door",
    30079: "save_attrs",
    30089: "take_key",
    29688: "open_door",
    29771: "close_door",
    30287: "draw_inventory",
    30375: "update_status",
    30751: "hag_colours",
    30903: "next_anim",
    30938: "two_frames",
    31415: "game_font",
    31436: "show_magic",
    31485: "show_lives",
    31949: "flag_off",
    31956: "flag_on",
    31963: "kill_monster",
    31970: "lose_magic",
    31988: "reset_hag",
    32194: "sound_down",
    32265: "sound_up",
    32333: "show_score",
    32349: "add_score_10",
    32512: "delay",
    32569: "enter_door",
    32905: "wait_key",
    32922: "load_slot",
    33211: "store_slot",
    33536: "tumble",
    33739: "spawn_monster",
    34517: "move_monsters",
    35270: "erase_monster",
    35524: "underground",
    36926: "look_around",
    37371: "enter_room",
    38249: "move_room_things",
    39278: "take_ingredient",
    39541: "smoke",
    39828: "menu",
    40051: "lose_life",
    40096: "respawn",
    40203: "print_score",
    40290: "draw_chest_bag",
    40581: "draw_ingredients",
    28089: "walk_gfx_step",  # from below ground's loop too: the walking graphic, then 27620
    29543: "door_x",         # x of the door from the grass bytes at 20672
    29860: "door_frame",
    30401: "print_key",
    30785: "draw_house",     # USR mc_draw+2: the house's inside
    30804: "draw_land",      # USR mc_draw: the landscape
    30817: "flying_gfx",
    30848: "set_hag_gfx",    # hag_gfx = hag_gfx_base + 72 * anim
    30872: "walking_gfx",
    30954: "door_sprite_set",
    31006: "door_frame_gfx",
    31055: "draw_door_frame",
    31138: "old_hag_sprite",
    31190: "erase_old_hag",
    31240: "hag_sprite",
    31292: "door_prbuff",
    31379: "draw_door",
    31687: "hag_not_drawn",
    31694: "hag_no_erase",
    31701: "hag_erase_on",
    31711: "hag_up",
    31724: "hag_right",
    31743: "hag_left",
    31767: "stick_up",       # flag = stick is 8, 1 or 2
    31826: "stick_down",     # 4..6
    31867: "stick_right",    # 2..4
    31908: "stick_left",     # 6..8
    32010: "monster_mode",
    32039: "clear_slots",
    32099: "clear_slot_q",
    32136: "ink4",
    32148: "ink5",
    32160: "walk_speed",
    32167: "fly_speed",
    32180: "x_back",
    32187: "stick_off",
    32410: "score_width",
    32477: "magic_floor",
    32500: "ink7",
    32867: "grounded",
    32877: "moon",
    32898: "o_type_off",
    34325: "big_monster",
    34344: "monster_life",
    34422: "walk_right",
    34448: "walk_left",
    35513: "menu_colours",
    36489: "room_edge",
    37197: "stand_check",
    37238: "jump_curve",
    37305: "x_to_edge",
    37312: "attr5",
    37345: "room_left",
    37355: "room_right",
    37515: "load_kind",      # the 8-byte record at 42274 + 8*kind into slot q
    39428: "erase_old_thing",
    39724: "erase_smoke",
    40134: "clear_slot",
    40917: "clear_slots_2",
}

# The Spectrum's system variables (and other fixed addresses) the program
# PEEKs and POKEs.
SYSVARS = {
    23296: "PRBUFF",        # the printer buffer: parameters for the machine code
    23297: "PRBUFF+1",
    23563: "DEFADD",        # the ROM's DEFADD, unused by a running program: the compiled RND's seed
    23606: "CHARS",
    23607: "CHARS+1",
    23672: "FRAMES",
    23693: "ATTR_P",
    23695: "ATTR_T",
    23728: "NMIADD",        # unused on a 48K: USR 51900 leaves the direction here
    23729: "NMIADD+1",      # ... and the fire button here
}

# Machine-code routines called with USR, by address.
USR = {
    42140: "end_text",       # the completion screen's text, in the game font
    45710: "draw_room",      # an underground room: PRBUFF = the room, PRBUFF+1 = 5
    50350: "game_over_text",
    50369: "menu_text",
    51675: "save_attrs",     # copies the attributes of rows 16-21 to 51700
    51687: "restore_attrs",  # ... and back
    51900: "read_stick",     # PRBUFF = control: direction to 23728 (0, 1 up .. 8 up-left), fire to 23729
    52852: "moon_attrs",     # repaints the moon's attributes (6 by 5 cells from row 7, column 6)
}
