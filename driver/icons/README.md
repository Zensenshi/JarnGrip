# Button icons

PNG files here are drawn on the pad's buttons in place of their labels, in the theme's lettering color. The pad uses
only each picture's shape (its transparency), so draw white (or any color) on a transparent background: a picture
without transparency shows as a solid square.

- 128 by 128 pixels, square, with about 12 pixels of margin.
- Named for the button's id: `map.png` for Map, `sit_stand.png` for Sit / stand, `chat_page_up.png`, and so on. Party 1
  to 4 share `party.png`, with their number beside it; the Chat button's is `chat_say.png`. WoW's buttons look for theirs
  (`_pictured` in driver/bin/pad_model.py); FFXI and Desktop show words.
- Copied next to the pad's driver when JarnGrip is installed; a button whose file is missing shows its label.

Icons here ship with JarnGrip: use your own designs, or icons whose license allows it, and credit them in NOTICE.md.
