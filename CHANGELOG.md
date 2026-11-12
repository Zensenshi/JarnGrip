# Changelog

## 0.10.0

- **A status card under the clock.** Tap the clock and battery and a card opens over the pad: the **network** (Wi-Fi name, signal, band and speed, the Thor's IP address, and whether the internet is reachable), the **battery** (charge, time left or until full, the watts it charges or draws at, its health and cycles) and the **temperatures** (CPU, GPU, battery, and the fan's speed). A touch anywhere closes it without pressing what is under it, and it closes by itself after 20 seconds so that it never sits on the screen. The pad sends nothing over the network to fill it: the internet check is NetworkManager's own.
- **Swipes keep up with your thumb in game.** Changing a number's swipe from up to left or down (or a target's swipe right) redrew late while a game was running: the pad asked for one redraw per change, and it waited its turn. While a finger is on a number or a target, the pad now repaints every frame, as the Chat radial does while it opens, but only the key and the fans or squares its swipes open; the rest of the pad is left alone. A Shift or Ctrl square fading after you lift repaints only its own area too.
- **Bigger swipe squares.** In icon mode, the Shift and Ctrl squares (FFXI: Ctrl and Alt) that open as you swipe are a third bigger than the keys, so they stand out; Cancel stays the keys' size. They grow from the key's corner away from each other, so they never overlap.
- **Japanese keyboard bindings for WoW.** Bindings made on a Japanese 106/109 keyboard sync to the Thor, where WoW reads the keys as US ones, so `^` (right of `-`) was out of reach. Type `/jarngrip jis` in WoW on the Thor: the pad's `=` key then does what `^` does, with Shift, Ctrl or Alt too (and `[` `]` `'` `\` do what `@` `[` `:` `]` do), and the pad labels it `^`. The addon does it with WoW's session-only override bindings: your saved bindings are never changed, and the desktop is left alone.
- **The icon page fits the screen.** Each tap's and swipe's name stays on one line beside its picture, however long what it holds in WoW is, and the buttons under them (Clear key, Clear all, Fill from file names, Look for new pictures, Done) wrap onto a second row instead of running off the right edge.
- **Remap a control works again.** Picking another control, a key or a modifier went straight back to Character: Steam closes and reopens the Quick Access menu around a dropdown's list, and the panel forgot what was picked each time. It now keeps it until you save.
- **Remap a control names the numbers by their key**: number 1 to number =, in place of slot 1 to slot 12.
- **The second modifier is now a swipe left, and a swipe down cancels.** On the number pad, swipe up for Shift (FFXI: Ctrl) as before, **left** for Ctrl (FFXI: Alt), and **down** to cancel, so that you swipe toward each one's square. The fans, the hint over the number pad and the one on the settings page point the new ways (the settings page's now names FFXI's Ctrl and Alt too). Pictures and profiles saved for a swipe down keep working: they are the swipe left's now.
- **WoW's chat radial in the game's colors.** Each channel's name on its petal is in the color WoW's chat gives it: Say white, Yell red, Whisper pink, Party blue, Raid and Instance orange, Guild green. The chosen petal is lettered like a pressed button, so it reads on every theme.
- **Icons on WoW's buttons.** Every button on WoW's Interface, Target and Utility pages shows an icon in place of its name: a helmet for Character, a map for Map, a crosshair with an arrow for Next and Previous enemy, and so on. Party 1 to 4 share one icon with their number beside it, and Chat shows a speech bubble, in the middle of its radial too; the chat channels keep their names. The icons are drawn in the theme's lettering color and light up with the button like its name did. FFXI and Desktop keep their words.
  - The icons are PNG files in `driver/icons`, one per button, named for it (`map.png`, `sit_stand.png`); a button whose file is missing shows its name.
- **A tidier Decky panel.** Enable, the status and Game stay at the top; the rest is in sections that open with a tap on their header (Opening the pad, Appearance and feel, Profiles, Remap a control, Number pad icons, Stop and uninstall). A closed section sums up what is set inside it, and the panel remembers which you left open.
- **Number pad icons**, like a Stream Deck. Pick **Icons** under **Number keys show** in Decky's **Number pad icons**, and the numbers become square keys with your own pictures on them, each with its number small in the corner. Each number can have a picture for its tap and one for each swipe: as soon as you swipe, squares open around the key in place of the fan, each where you swipe for it: Shift above, Ctrl to the left, a red Cancel below, each with its picture. The one you swipe toward lights up and the others stay faint. After you lift, the Shift or Ctrl square stays and fades over two seconds; a cancel goes at once. A key or swipe without a picture shows its number or the modifier's name as before, and the keys send what they always did.
  - The pictures go in a folder per game, `~/Pictures/JarnGrip/Icons/wow` and `~/Pictures/JarnGrip/Icons/ffxi`: PNG, JPEG or WebP, ideally square.
  - **Edit icons…** in Decky opens a full-screen page, out of the cramped side panel: the twelve numbers laid out as on the pad with their pictures, and beside them the tap's and both swipes' pictures of the one you pick, with previews.
  - Choosing a picture opens a grid of every picture in the folder, with a search box that narrows it by name.
  - **Fill from file names** sets up many keys at once: a picture named for a number and swipe goes on it, such as `5-fireball.png` for 5's tap or `5-shift-frostbolt.png` for its swipe up.
  - Each game remembers what its number keys show (**Numbers**, **Spell names** in WoW, or **Icons**), and each profile keeps its own icons along with its remaps.
- **Your WoW action bars on the number keys.** The new **JarnGrip addon** for WoW (in `wow-addon/`) saves what each key on your action bars holds, by your real key bindings, and the pad shows it on the numbers. By default (**Number keys show: Spell names**), each key shows the name of the spell, item or macro it casts, with its number small in the corner, and a swipe's fan names what that swipe casts. In icon mode, the icon's picture where one in your icon folder matches, or else the name, on the key and in its swipe squares; a picture you pick yourself still wins. Until the addon has saved your bars, and in FFXI, the keys show their numbers. **Use my WoW action bars** in Decky turns it off.
  - **No more /reload at every start.** When you log in and the pad's copy of your bars is out of date (first install, another character, or the game last closed from Steam's menu, which skips WoW's save), the addon offers a one-tap **Reload**. When the copy is current it stays quiet.
  - The addon only reads your bindings and bars, never during combat, and WoW writes its file when you log out or `/reload`. JarnGrip finds that file in Proton, Lutris, Heroic and Bottles installs on the Thor, or takes a copy in the icon folder.
  - Pictures match by WoW's icon number, by the icon's file name (with `icon-names.csv`, which `scripts/wow-icon-names.py` makes from the community listfile), or by the spell's name.
  - The icon page shows what came from WoW for each key, whose bars they are and when they were saved, and has **Clear all**.

## 0.9.0

- **A Desktop profile**, for the desktop, the web and anything else that is not a game. Pick **Desktop** under Game in Decky; it keeps its own remaps and profiles like the games do.
  - Two pages across the whole width, with no number pad. **Edit**: Undo, Redo, Cut, Copy, Paste, Select all, Find and Save, and beside them Esc, Delete, Tab, Enter, Home, End, Page up and down. **Browser**: Back, Forward, Reload, Address bar, New, Close, Previous, Next and Reopen tab, Bookmark, Zoom out and in, and beside them Switch window, Close window, Full screen, Screenshot, Menu, and a **Media** radial with Play / pause, Previous, Next, Volume down and up, and Mute, drawn as icons.
  - Paste, Save, Reload, New tab, Close tab, Reopen tab, Bookmark, Close window, Full screen and Screenshot send one keystroke per touch, so a resting thumb cannot close a row of tabs or paste over and over. The rest are held like the games' buttons, so Undo, Delete, Page down or Zoom in repeat while held.
  - The keyboard has **F1 to F12** in two rows above it, and Super and the arrow keys, laid out as on a keyboard, beside them, in place of the small trackpad. The keys themselves are the same size as in the games.
  - On the trackpad, **Back**, **Copy**, **Paste** and **Forward** replace Shift, Ctrl and Alt. **Pinch** to zoom (Ctrl and the wheel, as a browser takes a touchpad pinch): fingers that spread or pinch three times more than they travel, or with one kept still. Two fingers still scroll every way, two thumbs far apart included, and a two-finger tap still right-clicks. The games' trackpads are unchanged.
- **A Chat radial on the Utility page.** **Chat** is a big round button in the middle of the page's left half, and touching it opens a radial of channels out of its middle, like a flower. Slide onto one (it grows a little) and lift, or tap **Chat** and then tap a channel: the game's chat box opens on that channel while the pad switches to the keyboard, on the page you last left it. The red slice at the bottom cancels, and so does lifting in the middle, or tapping the middle or anywhere outside the radial.
  - **WoW**: Guild, Party, Yell, Raid, Instance, Say and Whisper. WoW has no key per channel, so the pad types the channel's command (`/g ` and so on) into the chat box. It never presses Enter: nothing is said until you send it.
  - **FFXI**: Linkshell, Party, Say and Reply, FFXI's own Ctrl shortcuts, one key each. Their remaps carry over.
- **Shorter Utility pages, in rows.** WoW's loses Auto-run, Walk / run, Hide UI and both nameplate toggles; FFXI's loses Auto-run, Rest and Point of view, which the controller already covers, and its four chat buttons, now in the radial. The rest pair up: WoW's Sheathe weapons and Screenshot share a row and Sit / stand has its own, above Chat, and Chat page up and down share one under it; FFXI's Macro set up and down share a row above Chat.
- **Two-finger scrolling stops when a finger lifts**, even when the touchscreen loses that lift: once the other finger has moved on its own for 0.3 s, the pad lets the lost one go and the finger left behind moves the pointer again. Before, it went on scrolling for 1.5 s.
- **Trackpad sensitivity** has moved up into Appearance and feel, beside the haptics, from the bottom of the panel.

## 0.8.0

- **Final Fantasy XI.** Pick the game in Decky: the pad lays out FFXI's default keys on Menus, Target and Utility pages. Each game keeps its own remapped controls and profiles; switching sets one game's aside and brings the other's back.
  - The number pad is FFXI's macro palette: swipe up for Ctrl (the upper bar), down for Alt (the lower one).
  - Swipe a party target (Self, Party 1 to 5) right to press Enter after it, so a spell cast on `<stpt>` goes off at once. An Enter fan opens while you swipe.
  - Macro set up and down change the set once per tap, however long you hold. Ctrl goes down well before the arrow, or FFXI takes the arrow for the camera.
- **The AYN button works after a reboot.** Decky starts before the user's session exists, so the backend could not open the channel the button's presses arrive on and never tried again. It now keeps trying, and opens it again if the session restarts.
- **The vibration motor no longer stays powered after a buzz.** In Desktop Mode, where InputPlumber holds the gamepad, the pad buzzes the `qcom-hv-haptics` motor directly. After the pad had buzzed it, that motor kept drawing about 1.6 W until the pad closed, and a spot on the back of the device grew too hot to touch. The pad now closes the motor and opens it again a second after the last buzz, which puts it back at rest. The gamepad that Game Mode uses is left as it was.
- **"Stop the screenshot" no longer takes the controller away.** It loads InputPlumber's profile with the target devices InputPlumber has at that moment, plus a keyboard. At boot, InputPlumber switches those devices as Steam starts, and a load in the middle of that left the keyboard as the only one: the controller did nothing until the Thor restarted. JarnGrip now changes the profile only while a gamepad is among them, and otherwise tries again a few seconds later. If the gamepad goes missing afterwards, it brings back the one that was there.

## 0.7.1

- **Opening and closing the pad is faster.** The Decky backend now reaches the user's service manager directly instead of through `systemd-machined`, and no longer runs a call a second time when its answer was "no". Together these added 1 to 3.5 seconds each way.
- The backend no longer holds up Decky while it waits on the system: service and InputPlumber calls run beside Decky's requests, start-up returns at once, and stopping gives up on its cleanup after 3 seconds rather than being killed by Decky.

## 0.7.0

- **Open and close the pad in one press**, from anywhere in Game Mode, a game included, so the bottom screen can go back to another app and come back to the pad without opening Decky. A toast says which.
  - **Home + Start** by default. **Change shortcut** in Decky records another button or combination, and the shortcut can be turned off.
  - **AYN button** (off by default): the button below the screen does it too. A small listener, `jarngrip-ayn.service`, hears it, because the Decky backend cannot read input devices.
  - **Stop the screenshot** (off by default): the AYN button no longer takes a screenshot. JarnGrip loads InputPlumber's profile again with that one button sending F24 instead; no file changes. JarnGrip applies it again each time it starts, and puts the old profile back when the setting is turned off or JarnGrip is uninstalled. The installer adds a polkit rule that allows this, and it applies only while JarnGrip is installed.
- **Uninstall JarnGrip** at the bottom of the Decky panel, using Decky's own uninstall. Uninstalling from Decky, there or in its settings, now also stops the pad, gives the bottom screen and the AYN button back, and removes the services and driver from the home folder, like the uninstall script. Settings and profiles are kept.

## 0.6.1

- The Decky option "Also run in Desktop Mode" is now "Start with Desktop Mode", which is what it does: the app-menu entry is there either way.

## 0.6.0

- **Game Glass** theme: frosted glass buttons over a picture from `~/Pictures/JarnGrip`, with an adjustable blur.
- **Desktop Mode**: the pad can run on the KDE desktop's bottom screen too, from the app menu or started with the desktop ("Also run in Desktop Mode" in Decky). Close pad gives the screen back to the desktop. Only one pad runs at a time.
- The number block no longer has a Shift / Ctrl / Alt row: swipes replace it. The trackpad view keeps its own.
- Swipe directions on a number: up for Shift, down for Ctrl, left to cancel (0.5.0 had left, right and up). A swipe to the right sends the plain number. Nothing now needs room right of the right-hand column, where the screen ends.
- A swipe on a number opens a rounded fan in its direction, dressed in the theme's colors, with the modifier written large in it, instead of a small bubble above the button. The fan fades into the key it opens from. Where the screen ends first (Ctrl on the bottom row), the fan is shorter. A guide above the number block shows the three directions, and fades like the other hints.
- Number keys are a little shorter (at most 1.1 times as tall as wide), and the number block is centered top to bottom.
- The header and its tabs are a little taller; the buttons below shrink to match.
- Each theme has its own lettering: Classic uses Cinzel and Game Glass the rounded Nunito, both bundled; Charcoal and Dark keep the system sans.
- The OLED theme is now called Dark, with darker key shading. A config that still says `oled` keeps working.
- Game Glass highlights are more translucent.
- The page tabs share one lettering size.
- Profiles in Decky list every saved profile, can be saved under a new name and deleted. The do-nothing "Compact" and "PvP" starter profiles are gone.
- Decky shows why the pad did not start or stop.
- **Unstick keys** on the gear page makes the game let go of Shift, Ctrl and Alt after it missed a key-up, as happens when Steam's overlay (Shift+Tab, WoW's default for Target Previous Enemy) opens mid-press.
- Haptics never hold up touch input, even if the daemon behind the vibration device stalls.
- A tap no longer holds up touch input: a key is still held down for at least 30 ms, but its key-up now comes from a timer instead of the touch reader waiting. Before, every number tap paused touch handling for 30 ms.
- The log no longer records each key press or which keyboard key was touched: together they spelled out everything typed.
- The log file moved from the shared `/tmp` to `/run/user/1000`, readable by the user alone, and starts over at 1 MB.
- The installers unpack into a fresh private folder instead of a fixed path in `/tmp`, refuse a source folder with symbolic links, and change files in the user's home as the user rather than as root.

## 0.5.0

- Number buttons send on release: swipe left for Shift, right for Ctrl, up to cancel.
- Decky remapping uses a named key list with Ctrl / Shift / Alt toggles instead of raw key codes.
- Burn-in protection (from Ratatoskr): a slow drift, fading hints and idle dimming.
- Haptic patterns: a press, a lighter tick, and a double buzz for locks.
- A clock and battery in the header.

## 0.4.0

- Renamed from Thor WoW Pad to **JarnGrip**; the installer migrates an existing install and its settings.
- Licensed under GPL-3.0.
- The installer keeps its backups outside Decky's plugins folder, where Decky could load them as duplicate plugins.
- The SteamOS theme is now called Charcoal.

## 0.3.0

- Themes: Classic, a Steam Deck–style theme and OLED, with shading that lifts the buttons off the background.
- Haptics, through the Thor's force-feedback devices.
- The keyboard sits lower, with a small trackpad above it, and shows the key under your thumb in a bubble.
- Larger lettering.

## 0.2.0

- Grabs only the bottom touchscreen. 0.1.0 could take the top screen's touchscreen, whose name also passed its test.
- A new input layer, copied from Ratatoskr.

## 0.1.0

- First version, as Thor WoW Pad: a port of AYN-Thor-WoW-Launcher's second-screen pad.
