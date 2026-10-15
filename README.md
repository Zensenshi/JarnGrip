# JarnGrip

A touch control pad for the AYN Thor's bottom screen, named after Járngreipr, Thor's iron gloves.

JarnGrip is a Decky Loader plugin for ArmadaOS. It runs a native GTK 3/Cairo pad on the lower screen and sends ordinary keyboard and mouse input, through `/dev/uinput`, to the game on the upper screen. The default layout is built for MMOs, with buttons that send World of Warcraft's default key bindings, and every button can be remapped.

The pad started as a Linux port of the second-screen pad in [AYN-Thor-WoW-Launcher](https://github.com/wyattabuntjer/AYN-Thor-WoW-Launcher), and its input layer comes from [Ratatoskr](https://github.com/venatrix-ritz/Ratatoskr). See [Credits](#credits).

## Features

- **Pages** on the left half: Interface, Target and Utility send WoW's default keys. A page with more than eight buttons splits into two columns. Page buttons are real keys: finger down presses, finger up releases, and several can be held at once.
- **Number block** (`1`–`9`, `0`, `-`, `=`) on the right half: action bar 1. A number is sent when your finger lifts, so a swipe can change it: **swipe up for Shift**, **swipe down for Ctrl** (action bars 2 and 3, if you bind them to Shift- and Ctrl-number), and **swipe left to cancel**; a swipe to the right sends the plain number. While you swipe, a fan opens from the button in that direction and names the modifier, and a guide above the number block shows the directions when the page opens.
- **Trackpad** (header button): move, tap to click, two fingers to scroll, a scroll strip along the right edge, and **Left click** / **Right click** buttons that stay pressed while held, so they drag and turn the camera. Double-tap a click button to keep it held. **Shift, Ctrl and Alt** above them arm a modifier for the next click; a double tap locks one until you tap it again.
- **Keyboard** (header button): letters, digits, one-shot Shift and Caps, and a `?123` page with symbols and arrow keys. The keys sit low for thumbs, under a small trackpad, and a held key shows its character enlarged above your thumb.
- **Settings** (gear button): the theme picker, which touchscreen and vibration motor the pad uses, **Unstick keys** (makes the game let go of a Shift, Ctrl or Alt it thinks is still held), and **Close pad**, which gives the bottom screen back without going through Decky.
- **Themes**: Classic (stone and gold, lettered in the Cinzel typeface), Charcoal (slate and blue), Dark (pure black) and **Game Glass**: frosted glass buttons over a picture of your choice, blurred just enough for the rounded Nunito lettering to read.
- **Haptics**: a buzz on every press, a lighter tick on page changes and swipe directions, and a double buzz when a modifier or click button locks.
- **Clock and battery** in the header.
- **Burn-in protection** for the OLED panel: the pad drifts by up to 1.5 px, the trackpad hints fade out, and the pad dims after a minute without a touch.
- **Decky panel**: start and stop the pad, choose a theme and picture, set haptics and trackpad sensitivity, remap any control with a named key list, and keep remaps as profiles.

## Install

You need an AYN Thor running ArmadaOS with [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader), and SSH access to it (Armada Tools → Remote Access shows the address).

**From a PC**, in a clone or download of this repository:

```sh
git clone https://github.com/Zensenshi/JarnGrip.git
cd JarnGrip
./scripts/install-from-pc.sh armada@THOR_IP
```

This copies the plugin over SSH and runs the on-device installer, which asks for the `armada` user's `sudo` password if it needs one. If you use an SSH key, make sure the `armada` account accepts it.

**On the Thor**, in a copy of this repository:

```sh
sudo ./scripts/install-on-device.sh
```

Then open **Steam menu → Decky → JarnGrip** and enable the pad.

The installer puts the plugin in `/home/armada/homebrew/plugins/jarngrip`, refuses to replace a different plugin there, keeps the three newest previous versions in `/home/armada/homebrew/jarngrip-backups` and restarts Decky. Decky then installs the pad's driver and user service under `/var/home/armada`. No packages are installed.

**Upgrading from Thor WoW Pad**, this plugin's earlier name: the installer stops and removes the old plugin and its service, gives back the screen services it had paused, and moves your settings and profiles to `~/.config/jarngrip`.

## Using it

The pad takes over the bottom screen. If Ratatoskr (`touch-master.service`) or Armada's own bottom-screen service is running, the plugin stops it while the pad runs and starts it again when you stop the pad. Don't run two bottom-screen drivers at once: they compete for the touchscreen.

**One press, one key.** Every button sends a single key, with its Shift, Ctrl or Alt, never a sequence of keys: Blizzard allows input software one action per keypress. For emotes or anything longer, make a macro in WoW (`/dance`), put it on an action bar, and press that slot from the pad.

**Remapping.** In Decky, under **Remap a control**, pick a control, a key from the named list and any of **With Ctrl**, **With Shift** and **With Alt**, then save. **Reset to default** puts a control back. A swipe on a number adds its Shift or Ctrl to whatever that number sends.

**Profiles.** A profile is a saved set of remaps. Pick one to load it, save the current remaps to it, save them as a new profile by name, or delete one.

**Game Glass pictures.** Put PNG, JPEG or WebP files in `~/Pictures/JarnGrip` on the Thor (for example with `scp`), choose Game Glass in Decky and pick a picture. Without one, the theme uses a built-in color wash.

### The config file

Everything is kept in `~/.config/jarngrip/config.json`, which the pad rereads within a second of a change. Decky writes most of it; these can also be set by hand:

| Key | Values | |
|---|---|---|
| `bindings` | `{control: key}` | `"slot_1": "ctrl+59"` sends Ctrl+F1; `"previous_enemy": "33"` sends a plain F. Keys are [Linux key codes](https://github.com/torvalds/linux/blob/master/include/uapi/linux/input-event-codes.h). A bare number replaces the key but keeps the button's own Shift or Alt. Controls are the page buttons (`character`, `quest_log`, `previous_enemy`, …) and `slot_1` to `slot_12`. |
| `theme` | `classic`, `charcoal`, `dark`, `glass` | |
| `background_image`, `glass_blur` | a file name in `~/Pictures/JarnGrip`; 1 to 5 (3) | The Game Glass picture and how strongly it is blurred. |
| `sensitivity`, `scroll_speed` | 0.2 to 3 (1); 1 to 5 (3) | Trackpad pointer speed and two-finger scroll speed. |
| `tap_to_click`, `glide` | `true` / `false` | Trackpad taps click (on); the pointer keeps gliding after a flick (off). |
| `haptics`, `haptics_strength`, `haptics_ms` | on/off; 0.05 to 1 (1); 5 to 100 (40) | Buzz strength and length. |
| `haptics_effect` | `rumble`, `constant`, `periodic` | Forces one force-feedback effect type. By default a gamepad gets `rumble` and a bare haptics motor `constant`. |
| `burn_in`, `dim_after_s`, `dim_level` | on/off; seconds (60); 0.1 to 1 (0.4) | Burn-in protection, and when and how far the idle pad dims. |
| `clock_24h` | `true` / `false` | A 24-hour clock in the header. |
| `desktop_mode` | `true` / `false` | Start the pad with the desktop in Desktop Mode ("Also run in Desktop Mode" in Decky). |

## Game Mode and Desktop Mode

In Game Mode the pad is `jarngrip.service`, bound to `armada-bottom-gamescope.service`, with `Restart=no` and `Conflicts=` on `touch-master.service` and `armada-bottom-screen.service`. Switching to Desktop Mode stops it along with the bottom gamescope session, without any restart loop, and Decky never starts it by itself after a reload ([Ratatoskr issue #34](https://github.com/venatrix-ritz/Ratatoskr/issues/34)). Back in Game Mode, enable it again from Decky.

**In Desktop Mode** the pad runs as an ordinary app on the KDE desktop, fullscreen on the bottom screen, without taking the keyboard focus from your game. Start it from the app menu (**JarnGrip**), or turn on **Also run in Desktop Mode** in Decky to have it start with the desktop. **Close pad** quits it and gives the bottom screen's touch back to the desktop. Only one pad runs at a time. Its log is `/run/user/1000/jarngrip-debug.log`.

## Uninstall

On the Thor, `sudo ./scripts/uninstall-on-device.sh`, or from a PC, `./scripts/uninstall-from-pc.sh armada@THOR_IP`. This stops the pad, restores the screen services it had paused, removes the plugin, its service, driver and backups, and restarts Decky. Your settings and profiles stay in `~/.config/jarngrip/`.

## Troubleshooting

- The gear page shows which touchscreen and vibration motor the pad uses, and where the last touch landed.
- Log: `journalctl --user -u jarngrip.service -n 80 --no-pager`, or the file `/run/user/1000/jarngrip-debug.log`, which only you can read. `DBG-200` names the touchscreen, `DBG-201` means none was found, `DBG-203` means another driver holds it, `DBG-501` logs each touch (on the keyboard without its key or position, so the log never records what you type), `DBG-800` names the vibration device and `DBG-801` says why none could be used.
- **The touchscreen**: the pad grabs only a device whose name contains both `bottom` and `touchscreen` (`bottom_touchscreen` on Armada), never any other, and keeps looking every few seconds until one appears.
- **Haptics** use the first input device that can play force-feedback effects, gamepads first. On the Thor that is InputPlumber's virtual `Microsoft X-Box 360 pad`, which passes rumble on to the controller's motor (the same buzz as Steam's keyboard); the fainter `qcom-hv-haptics` motor is the fallback. The `armada` user needs write access to that `/dev/input/event*` node. While no motor is usable, the pad looks again every 10 s.
- **Previous enemy opens the Steam menu**: WoW's default for Target Previous Enemy is Shift+Tab, which is also Steam's overlay shortcut. Bind it to something else in WoW (for example Ctrl+Tab under Keybindings → Targeting) and remap `previous_enemy` to match in Decky.
- **Numbers switch action bars, or keys act as if Shift, Ctrl or Alt were held**: the game missed a key-up, usually because Steam's overlay opened mid-press. Tap **Unstick keys** on the gear page.
- **A stuck key**: a button whose finger has reported nothing for 4.5 s is let go. This guards against the Thor's touch controller losing a finger-lift.

## Development

`python3 tests/test_jarngrip.py` (or `pytest`) runs the tests: the layout, the input rules, the choice of touchscreen and vibration motor, the Decky backend's config handling, and the painter in every theme against a stand-in for cairo. They need no device, GTK or cairo.

| Path | |
|---|---|
| `main.py`, `dist/index.js`, `plugin.json` | The Decky backend and panel. |
| `driver/bin/jarngrip.py` | The pad's window, touchscreen reader and lifecycle. |
| `driver/bin/pad_model.py` | What is on the screen and what each touch does. No GTK or cairo. |
| `driver/bin/pad_draw.py` | How it looks: themes and painting with cairo. |
| `driver/bin/haptics.py`, `system_status.py`, `touch_device.py` | Vibration, clock and battery, and finding the touchscreen. |
| `driver/bin/engine.py`, `touch_frames.py`, `burn_in.py`, `driver/debug_codes.py` | From Ratatoskr. |
| `driver/fonts/` | Cinzel and Nunito, Bold, under the SIL Open Font License. |
| `systemd/jarngrip.service`, `desktop/`, `scripts/` | The Game Mode service, the Desktop Mode menu and autostart entries, and the install and uninstall scripts. |

See [CHANGELOG.md](CHANGELOG.md) for what changed in each version.

## Credits

- [Ratatoskr](https://github.com/venatrix-ritz/Ratatoskr) by Ven (venatrix-ritz) and Thor Input Contributors (MIT): the virtual mouse and keyboard, the trackpad gesture engine, the touch-frame parser, the burn-in protection and the debug codes are copied from it, and the touchscreen handling follows it.
- [Project Barry](https://github.com/project-barry/barry-launcher) by lavachemist, which Ratatoskr credits for its gesture math and bottom-screen input design.
- [AYN-Thor-WoW-Launcher](https://github.com/wyattabuntjer/AYN-Thor-WoW-Launcher) by wyattabuntjer (GPL-3.0), whose second-screen pad this ports, and the projects it forks: [WoW Forever for Android](https://github.com/jaredgei/wow-forever-android) by jaredgei and [GameNative](https://github.com/utkarshdalal/GameNative).
- The [Cinzel](https://github.com/NDISCOVER/Cinzel) and [Nunito](https://github.com/googlefonts/nunito) typefaces (SIL Open Font License 1.1).
- [Armada OS](https://armadaos.dev), [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) and [InputPlumber](https://github.com/ShadowBlip/InputPlumber), which the pad runs on and works with.

[NOTICE.md](NOTICE.md) lists which file came from where.

## License

Copyright (C) 2026 Zensenshi. JarnGrip is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License, version 3, as published by the Free Software Foundation. See [LICENSE](LICENSE). It is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY.

Each source file says which license it is under (an `SPDX-License-Identifier` line). The files copied from Ratatoskr keep their MIT license, included in [`driver/RATATOSKR-MIT-LICENSE.txt`](driver/RATATOSKR-MIT-LICENSE.txt). World of Warcraft is a trademark of Blizzard Entertainment and is named only to describe compatibility. This is an unofficial project, not affiliated with or endorsed by Blizzard, Valve or AYN.

**Use at your own risk.** JarnGrip sends ordinary keyboard and mouse input, one key per press, but whether a game's rules allow a given input tool is up to its publisher, and JarnGrip comes with no warranty.
