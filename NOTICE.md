# Attribution and licensing

JarnGrip (formerly Thor WoW Pad) builds on other people's work. This file says what came from where.

JarnGrip is licensed under the GNU General Public License, version 3 ([LICENSE](LICENSE)). The files copied from Ratatoskr remain under their MIT license, which is compatible with the GPL and is included unchanged.

## Ratatoskr (MIT)

[Ratatoskr](https://github.com/venatrix-ritz/Ratatoskr) by Ven (venatrix-ritz) and Thor Input Contributors, MIT License. Its license, copyright notice and upstream credits are included unchanged in [`driver/RATATOSKR-MIT-LICENSE.txt`](driver/RATATOSKR-MIT-LICENSE.txt).

| File here | Relationship to Ratatoskr |
|---|---|
| `driver/bin/engine.py` | Copied unchanged: the virtual mouse and keyboard (uinput) and the trackpad gesture engine |
| `driver/bin/touch_frames.py` | Copied unchanged: the multitouch frame parser |
| `driver/bin/burn_in.py` | Copied unchanged: OLED burn-in protection (drift, hint fade, idle dimming) |
| `driver/debug_codes.py` | Copied; changed log path, added the 8xx haptics codes |
| `driver/bin/touch_device.py` | Written for this project, following `bin/thor_app.py` for finding, grabbing and reading the bottom touchscreen |
| `driver/bin/jarngrip.py` | Written for this project; its touch reader and shutdown follow `bin/thor_app.py` |
| `main.py` | Written for this project; drives the user service with the same `systemctl --machine=armada@.host --user` approach as Ratatoskr's Decky backend |

## Project Barry (credited through Ratatoskr)

Ratatoskr credits [Project Barry / Barry Launcher](https://github.com/project-barry/barry-launcher) by lavachemist and the Project Barry community for the gesture mathematics, coordinate transforms and bottom-screen input architecture in `engine.py`. That credit carries over here with the copied code.

## AYN-Thor-WoW-Launcher (GPL-3.0)

The pad's layout, behavior and Classic theme (`driver/bin/pad_model.py`, `driver/bin/pad_draw.py`) are a Python/Cairo port of the second-screen pad in [AYN-Thor-WoW-Launcher](https://github.com/wyattabuntjer/AYN-Thor-WoW-Launcher) by wyattabuntjer, GPL-3.0. That launcher is a fork of [WoW Forever for Android](https://github.com/jaredgei/wow-forever-android) by jaredgei, which is itself a fork of [GameNative](https://github.com/utkarshdalal/GameNative).

The port was written by reading the launcher's Kotlin source, and it follows it closely: the page and button lists with their default keys, the layout rules, the modifier, click-button and keyboard behavior, and the Classic theme's color values. No Kotlin source file or image from the launcher is included, but a port this close is treated as a derivative work of a GPL-3.0 project, which is why JarnGrip as a whole is licensed under GPL-3.0.

Written for this project and not ported: the Charcoal, Dark and Game Glass themes, button shading, haptics (`driver/bin/haptics.py`), the keyboard's trackpad and key previews, number swipes, the key picker, the header clock and battery (`driver/bin/system_status.py`), and the Game Glass theme.

## Fonts (SIL Open Font License 1.1)

| File | |
|---|---|
| `driver/fonts/Cinzel-Bold.ttf` | [Cinzel](https://github.com/NDISCOVER/Cinzel), Copyright 2020 The Cinzel Project Authors. License: `driver/fonts/Cinzel-OFL.txt`. |
| `driver/fonts/Nunito-Bold.ttf` | [Nunito](https://github.com/googlefonts/nunito), Copyright 2014 The Nunito Project Authors. License: `driver/fonts/Nunito-OFL.txt`. |

Both were taken from the variable fonts in [google/fonts](https://github.com/google/fonts) and reduced to their Bold instance (fontTools' instancer), the only weight the pad uses. Neither font declares a Reserved Font Name. The fonts are not covered by JarnGrip's GPL: they stay under the OFL.

## Platform

- [Armada OS](https://armadaos.dev) by the Armada Linux team provides `armada-run-bottom` and the bottom-screen gamescope session and services the pad runs in.
- [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) by the SteamDeckHomebrew community (GPL-3.0) is the plugin runtime that `main.py` and `dist/index.js` are written for.
- Haptics rumble the virtual gamepad that [InputPlumber](https://github.com/ShadowBlip/InputPlumber) (ShadowBlip) exposes on ArmadaOS. No InputPlumber code is included.

## Trademarks

The project includes no World of Warcraft or Blizzard assets, game files, fonts, logos or executables, and no Valve assets. World of Warcraft is a trademark of Blizzard Entertainment; Steam and SteamOS are trademarks of Valve Corporation; AYN Thor is a product of AYN. These names are used only to describe compatibility. This is an unofficial community project, not affiliated with or endorsed by any of them.
