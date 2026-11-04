# Changelog

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
