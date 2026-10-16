# Changelog

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
