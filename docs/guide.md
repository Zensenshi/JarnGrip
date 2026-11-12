# JarnGrip guide

## The pad

- **Pages**, on the left half, send the game's default keys: Interface, Target and Utility for WoW; Menus, Target and Utility for FFXI. The Desktop profile has no number pad, so its two pages take the whole width: **Edit** (editing on the left, Esc, Delete, Tab, Enter, Home, End and Page up / down on the right) and **Browser** (the browser on the left, windows, Screenshot, Menu and Media on the right). A page button is a real key: it is held while your finger is down, and several can be held at once. The Desktop shortcuts that would do harm if they repeated (Paste, Save, Reload, New tab, Close tab, Reopen tab, Bookmark, Close window, Full screen and Screenshot) send one keystroke per touch instead, however long your finger stays.
  - **FFXI's party targets** (Self, Party 1 to 5): a tap picks the member; swipe **right** to press Enter after it, so a spell cast on `<stpt>` goes off at once. An **Enter** fan opens while you swipe.
  - **FFXI's Macro set up / down** change the set once per tap, however long you hold: Ctrl goes down a moment before the arrow, or FFXI would take the arrow for the camera.
  - **Chat**, the big round button in the middle of the Utility page: touch it and a radial of chat channels opens out of its middle, like a flower. Slide onto a channel, which grows a little, and lift; or tap **Chat**, which leaves the radial open, and then tap a channel. Either way the game's chat box opens on that channel and the pad switches to the keyboard, on whichever page you last left it. The red slice at the bottom is **Cancel**; lifting in the middle or on an empty slice, or, while the radial is open, tapping its middle or anywhere outside it, also sends nothing.
    - **WoW**: Guild (up), Party, Yell, Raid, Instance, Say and Whisper, clockwise. WoW has no key for each channel, so the pad types the channel's command (`/g `, `/p `, …) into the chat box. It never presses Enter: nothing is said until you send it. Whisper leaves the name to you. Each channel's name is in the color WoW's chat uses for it (Say white, Yell red, Whisper pink, Party blue, Raid and Instance orange, Guild green); if you changed those colors in the game, the pad still shows the defaults. With the bundled icon, the Chat button shows a speech bubble in place of its name.
    - **FFXI**: Linkshell (up), Party (up-right), Say (left) and Reply (up-left), each FFXI's own Ctrl shortcut, so every slice is one key. They can be remapped in Decky as before.
  - **Media**, the round button on the Desktop profile's Browser page, opens the same way, with an icon on each slice: Play / pause (up), Next (up-right), Volume up (right), Mute (down-left), Volume down (left) and Previous (up-left). It sends the key and stays on the page. Previous and Next are the media track keys: music players use them, and YouTube only in a playlist.
- **Icons**: in WoW, the page buttons show icons in place of their names (Party 1 to 4 share one, with their number beside it), and Chat shows a speech bubble. The chat channels on its radial keep their names. FFXI and Desktop show words.
- **Number pad**, on the right half (not on the Desktop profile). A number is sent when your finger lifts, so a swipe can change it: **up** and **left** add a modifier, **down** cancels, and **right** sends the plain number. A fan opens in the swipe's direction and names what lifting will send.
  - **WoW**: action bar 1. Up adds Shift, left adds Ctrl. Bind action bars 2 and 3 to Shift- and Ctrl-number in WoW to reach them this way.
  - **FFXI**: the macro palette. Up adds Ctrl (the upper macro bar), left adds Alt (the lower one). A tap sends the bare number.
  - **With icons** (see [Number pad icons](#number-pad-icons)), the numbers are square and show your pictures, and a swipe opens squares around the key instead of the fan, each where you swipe for it: Shift above (WoW) and Ctrl to the left, a third bigger than the keys so they stand out, and a red Cancel below, the keys' size. The one you are swiping toward lights up. After you lift, the Shift or Ctrl square stays and fades over two seconds, so you see what was sent; a cancel goes at once.
- **Trackpad** (header button): move, tap to click, two fingers to scroll, a scroll strip along the right edge, and **Left click** / **Right click** buttons that stay pressed while held, so they drag and turn the camera. Double-tap a click button to keep it held. **Shift, Ctrl and Alt** arm a modifier for the next click; a double tap locks one until you tap it again.
  - **Desktop**: **Back**, **Copy**, **Paste** and **Forward** take the place of Shift, Ctrl and Alt (Back and Forward are Alt + Left and Alt + Right). Spread two fingers apart or pinch them together to zoom in or out, one step per few millimetres. Two fingers still scroll in every direction, and a two-finger tap still right-clicks.
- **Keyboard** (header button): letters, digits, one-shot Shift and Caps, and a `?123` page with symbols and arrow keys, under a small trackpad. A held key shows its character above your thumb.
  - **Desktop**: in place of the small trackpad, F1 to F12 in two rows of six, and to their right Super and the arrow keys, Up above Down as on a keyboard. Super is the Windows-logo key: in KDE Plasma it opens the application launcher.
- **Settings** (gear button): the theme, which touchscreen and vibration motor the pad uses, **Unstick keys**, and **Close pad**, which gives the bottom screen back without going through Decky.

## The Decky panel

**Enable JarnGrip**, the status and **Game** are always at the top. Everything else is in sections that open and close with a tap on their header: **Opening the pad**, **Appearance and feel**, **Profiles**, **Remap a control**, **Number pad icons**, and **Stop and uninstall**. A closed section says what is set inside it (the shortcut, the theme and haptics, the current profile, how many controls are remapped, whether icons are on), and the panel remembers which ones you left open.

- **Game**: World of Warcraft, Final Fantasy XI or Desktop. Each keeps its own remapped controls and profiles: switching sets one aside and brings the other's back.
- **Shortcut**: **Home + Start** opens or closes the pad from anywhere in Game Mode, mid-game included, without opening Decky. A toast says which. **Change shortcut** records the next button or buttons you press instead, such as the AYN button below the screen; **Back to Home + Start** undoes it. Turn the shortcut off here if a game needs that combination.
- **AYN button**: the button below the screen opens or closes the pad too. Steam still takes a screenshot each time unless you also turn on **Stop the screenshot**. Until then, **Home + R1** opens and closes the pad as well, because that is what the AYN button sends when InputPlumber emulates a Steam Deck controller.
- **Stop the screenshot**: the AYN button sends F24, a key nothing uses, instead of the screenshot. JarnGrip does this by loading InputPlumber's profile again with that one button changed; no file changes. It stays until you turn it off or uninstall JarnGrip: InputPlumber forgets it when it restarts, and JarnGrip applies it again each time it starts.
- **Theme**, **haptics** strength, **trackpad sensitivity** (how far the pointer moves for a finger's travel, 0.2× to 3×; 1× by default), **burn-in protection**, a **24-hour clock**, and **Start with Desktop Mode**.
- **Remap a control**: pick a control, a key and any of **With Ctrl / Shift / Alt**, then save. **Reset to default** puts it back.
- **Number pad icons**: **Show icons**, **Use my WoW action bars** (WoW only), and **Edit icons…**, which opens a full-screen page to pick a picture for each number's tap and swipes (see below). Not on the Desktop profile, which has no number pad.
- **Profiles**: saved sets of remaps and number pad icons for the current game. Load one, save to it, save as a new profile, or delete one.
- **Stop and restore screen services**, and **Uninstall JarnGrip**, which uses Decky's own uninstall: it stops the pad, gives the bottom screen and the AYN button back, and removes JarnGrip, keeping your settings and profiles.

While the pad runs, it stops Ratatoskr or Armada's own bottom-screen service, and starts it again when you stop the pad. Don't run two bottom-screen drivers at once.

## Game Glass pictures

Put PNG, JPEG or WebP files in `~/Pictures/JarnGrip` on the Thor (for example with `scp`), choose **Game Glass** in Decky and pick a picture. **Glass blur** sets how strongly it is blurred. Without a picture, the theme uses a built-in color wash.

## Number pad icons

Each game has its own folder of icons: `~/Pictures/JarnGrip/Icons/wow` and `~/Pictures/JarnGrip/Icons/ffxi` on the Thor. Decky makes the current game's folder the first time you open the panel. Copy PNG, JPEG or WebP files into it (for example with `scp`), turn on **Show icons** under **Number pad icons** in Decky and press **Edit icons…**.

The icon page fills the screen: the twelve numbers on the left, laid out as on the pad with their pictures, and on the right the pictures of the number you picked. Press a number, then **Tap**, **Swipe up** or **Swipe left**: a picker opens with every picture in the folder, and a **Search** box that narrows them to those whose names have every word you type (`frost nova` finds `Frost_Nova.png`). Press a picture to put it there, or **None** to leave the number or the modifier's name showing; B or **Cancel** closes the picker. Each choice is saved at once. **Clear key** removes the number's three pictures, **Look for new pictures** reads the folder again after you copy more in, and **Done** (or B) goes back. Pictures over 256 KB show their name only, without a preview.

**Fill from file names** sets up many keys at once: it puts every picture named for a number, and maybe a swipe, on it. The name starts with the number (`1` to `9`, `0`, `minus` or `equals`), then optionally the swipe (`up`, `left`, or the modifier: `shift` or `ctrl` in WoW, `ctrl` or `alt` in FFXI), then anything you like, separated by dashes, underscores or spaces (`down`, from before swipes went left, still means the second modifier):

| File | Goes on |
|---|---|
| `5.png`, `5-fireball.png` | 5's tap |
| `5-shift-frostbolt.png`, `5 up frostbolt.png` | 5's swipe up (Shift in WoW) |
| `minus_ctrl_blink.png`, `minus-left-blink.png` | -'s swipe left in WoW (Ctrl) |
| `0-alt-cure.png` | 0's swipe left in FFXI (Alt) |

It replaces what those keys showed and leaves the others alone. Where two pictures are named for the same key, the first in alphabetical order wins.

**Finding pictures.** Pictures named for the game's icon files (`spell_nature_lightning.png`) match your bars by themselves once `icon-names.csv` is in the folder (see below). The games' icons are their publishers' artwork, so JarnGrip ships none. In any version of WoW, a spell's page on [Wowhead](https://www.wowhead.com) shows its icon and the icon's name, and [wago.tools](https://wago.tools) exports the game's icons as PNG. FFXI's are on [BG Wiki](https://www.bg-wiki.com). The games' own icons are small (64 px or less, 32 px in FFXI), so unless upscaled they look soft on a key; [game-icons.net](https://game-icons.net) has thousands of sharp fantasy icons, free under CC BY 3.0. The pad follows your action bars: tap is action bar 1 in WoW, swipe up the bar you bound to Shift and a number, swipe left the one bound to Ctrl.

- Square pictures look best, about 200 pixels across. A picture that is not square is cut down to the square in its middle.
- At rest a key shows its tap's picture with its number small in the corner, like the hotkey on an action bar. A swipe opens the squares around the key, Shift above, Ctrl to the left and Cancel below, with their pictures and the modifiers' names; the chosen one is lit. On the top row the Shift square goes over the page tabs, and on the bottom row Cancel goes over the key itself.
- Icons belong to a number and a swipe, not to a key: remapping a number keeps its pictures.
- Saving a profile saves its icons with its remaps, and loading one brings them back, so a profile per character or spec can show that character's spells.
- JarnGrip ships no pictures for the numbers (its own button icons are another matter: see NOTICE.md). The games' own artwork belongs to their publishers; use pictures you have the right to use.
- Pictures must be PNG, JPEG or WebP. Icons taken from the game's files are BLP, Blizzard's own format, which the picker does not list: convert them to PNG first, for example with Pillow, which reads BLP.

### Your WoW action bars on the keys

With the **JarnGrip addon** in WoW, the numbers follow your action bars by themselves: a key without a picture of its own shows the icon of what that key casts in the game, or, where no picture matches, its name (the spell, item, macro, mount or key binding). It follows your real key bindings, remaps included: if you bound Shift-number to action bar 2, a swipe up shows bar 2.

1. **Install the addon.** Copy the `wow-addon/JarnGrip` folder (in JarnGrip's download, or `~/homebrew/plugins/jarngrip/wow-addon/JarnGrip` on the Thor) into the `Interface/AddOns` folder of the version of WoW you play, so that you have `World of Warcraft/_retail_/Interface/AddOns/JarnGrip/JarnGrip.toc` (or `_forever_` for WoW Forever, `_classic_era_` and so on). If WoW says it is out of date, tick **Load out of date AddOns** in the AddOns list; if it says it is incompatible, your version's number is missing from the first line of `JarnGrip.toc`: see what other addons there list.
2. **Let it save.** WoW writes what the addon saved when you log out, exit, or type `/reload`. Type `/jarngrip` in the game to see how many keys it saw. Change your bars, then `/reload` again to update the pad.
   - When you log in and the pad's copy is out of date (the first time, after switching characters, or when the game was last closed from Steam's menu rather than WoW's own **Exit Game**, which skips the save), the addon asks whether to reload: tap **Reload**. Quit with WoW's **Exit Game** or **Log Out** and the next start needs nothing.
3. **Turn it on.** **Show icons** and **Use my WoW action bars** (on by default) under **Number pad icons** in Decky. The pad picks up a new save within a few seconds, and the icon page shows what came from WoW for each key.

Where WoW runs on the Thor (Steam with Proton, Lutris, Heroic or Bottles), JarnGrip finds the addon's file itself, under `WTF/Account/<account>/SavedVariables/JarnGrip.lua`. If you stream the game from another computer, copy that file into `~/Pictures/JarnGrip/Icons/wow` after playing. When there are several, the newest one wins, and the pad shows the bars of the character you played last.

**Matching pictures to WoW's icons.** WoW names each icon by a number. A picture is used for a key when its name is that number (`136048.png`), the icon's file name (`spell_nature_lightning.png`, as icons exported from the game are named) or the name of what the key holds (`Lightning Bolt.png`); case, spaces, dashes and underscores do not matter. Matching by the icon's file name needs a list that pairs the numbers with the names: run `python3 scripts/wow-icon-names.py` on a computer, which downloads the community's list of game files ([wowdev/wow-listfile](https://github.com/wowdev/wow-listfile)) and keeps only the icons, and copy the `icon-names.csv` it makes into `~/Pictures/JarnGrip/Icons/wow`.

- A picture you pick on the icon page (or with **Fill from file names**) wins over WoW's. **Clear key** or **Clear all** on the icon page lets WoW's show again.
- The addon reads your bindings and action bars: it sends no keys and presses no buttons, and it never saves during combat. The only thing it changes is what a few keys do for the session, and only with **Japanese keyboard bindings** (below) on. JarnGrip reads its file from the disk, never from the game, the way companion apps like Raider.IO's and WeakAuras' do. Blizzard allows addons, as long as they are free and not obfuscated (its UI Add-On Development Policy); check that policy if in doubt.
- The pad shows the bars as they were when WoW last saved, not live: a druid's forms or a rogue's stealth show the bar you were on then.

**Japanese keyboard bindings.** WoW keeps your key bindings with your account, so bindings made on a Japanese (JIS, 106/109 key) keyboard come with you to the Thor, where WoW reads the keys as a US keyboard. There, the key right of `-` is `=`, not `^`, so the pad's last number key would do nothing. Type `/jarngrip jis` in WoW on the Thor, then tap **Reload**: from then on, each key does what the key in its place does on a JIS keyboard, with Shift, Ctrl or Alt too:

| The pad sends (US) | Does what this does (JIS) |
|---|---|
| `=` | `^` |
| `[` | `@` |
| `]` | `[` |
| `'` | `:` |
| `\` | `]` |

So a swipe up on the last number key is Shift + `^`, as on your desktop. The pad labels that key `^` and shows the icons of your `^` bindings. Your bindings themselves are never changed: the addon sets these for the session only, and WoW neither saves nor syncs them. The switch is kept in this WoW install's own files, so the desktop is left alone. `/jarngrip jis off` turns it off.

## Desktop Mode

Start **JarnGrip** from the desktop's app menu, or turn on **Start with Desktop Mode** in Decky to have it open by itself whenever Desktop Mode starts. The pad opens fullscreen on the bottom screen without taking the keyboard focus from your game. **Close pad** gives the bottom screen back to the desktop.

## Troubleshooting

- **Previous enemy opens the Steam menu.** WoW's default for Target Previous Enemy is Shift+Tab, also Steam's overlay shortcut. In WoW, bind it to Ctrl+Tab (Options → Keybindings → Targeting); in Decky, remap **previous enemy** to Tab with Ctrl.
- **Numbers switch action bars, or keys act as if Shift, Ctrl or Alt were held.** The game missed a key-up, usually because Steam's overlay opened mid-press. Tap **Unstick keys** in the settings.
- **No vibration.** The settings page shows which device the pad uses for haptics, or why it found none.
- **The pad doesn't react to touch.** The settings page shows which touchscreen it took and where the last touch landed.
- **Logs**: `journalctl --user -u jarngrip.service -n 80 --no-pager`, or `/run/user/1000/jarngrip-debug.log` (readable by you alone). The log never records which keyboard keys you type.

## Upgrading from Thor WoW Pad

JarnGrip's earlier name. Installing JarnGrip removes the old plugin and moves your settings and profiles to `~/.config/jarngrip`.

## Installing on the Thor itself

In a copy of this repository on the Thor: `sudo ./scripts/install-on-device.sh`, and `sudo ./scripts/uninstall-on-device.sh` to remove it.

## The settings file

Everything is kept in `~/.config/jarngrip/config.json`, which the pad rereads within a second of a change. Decky writes most of it; these can also be set by hand:

| Key | Values | |
|---|---|---|
| `bindings` | `{control: key}` | `"slot_1": "ctrl+59"` sends Ctrl+F1; `"previous_enemy": "33"` sends a plain F. Keys are [Linux key codes](https://github.com/torvalds/linux/blob/master/include/uapi/linux/input-event-codes.h). A bare number replaces the key but keeps the button's own Shift or Alt. Controls are the page buttons (`character`, `quest_log`, `previous_enemy`, …), FFXI's chat slices (`linkshell_chat`, `party_chat`, `say`, `reply_to_tell`) and `slot_1` to `slot_12`. |
| `theme` | `classic`, `charcoal`, `dark`, `glass` | |
| `wow_bars` | `true` / `false` (`true`) | In WoW with icons on, keys without a picture of their own show what the action bars hold (the JarnGrip addon). |
| `number_icons`, `icons` | `true` / `false`; `{icon: file name}` | Number pad icons. An icon is `slot_1` to `slot_12` for a number's tap, with `:up` or `:down` for a swipe (`"slot_5:up": "fireball.png"`); the file is in the game's folder in `~/Pictures/JarnGrip/Icons`. Both are kept per game, and the icons with each profile. |
| `background_image`, `glass_blur` | a file name in `~/Pictures/JarnGrip`; 1 to 5 (3) | The Game Glass picture and its blur. |
| `sensitivity`, `scroll_speed` | 0.2 to 3 (1); 1 to 5 (3) | Trackpad pointer speed and two-finger scroll speed. |
| `tap_to_click`, `glide` | `true` / `false` | Trackpad taps click (on); the pointer keeps gliding after a flick (off). |
| `haptics`, `haptics_strength`, `haptics_ms` | on/off; 0.05 to 1 (1); 5 to 100 (40) | Buzz strength and length. |
| `haptics_effect` | `rumble`, `constant`, `periodic` | Forces one force-feedback effect type. |
| `burn_in`, `dim_after_s`, `dim_level` | on/off; seconds (60); 0.1 to 1 (0.4) | Burn-in protection, and when and how far the idle pad dims. |
| `clock_24h` | `true` / `false` | A 24-hour clock. |
| `desktop_mode` | `true` / `false` | Start the pad with the desktop in Desktop Mode. |
| `ayn_button` | `true` / `false` | The AYN button below the screen opens and closes the pad, and Home + R1 while it still takes screenshots (off). |
| `ayn_no_screenshot` | `true` / `false` | The AYN button sends F24 instead of taking a screenshot, while `ayn_button` is on (off). |
| `shortcut`, `shortcut_buttons` | on/off; `[buttons, upper]` | The shortcut that opens and closes the pad in Game Mode (on), as Steam's two button bitmasks (Home + Start). Set it with **Change shortcut**. |
