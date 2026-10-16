# JarnGrip

A touch control pad for the AYN Thor's bottom screen, built for World of Warcraft and other MMOs. Named after Járngreipr, Thor's iron gloves.

JarnGrip is a [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) plugin for ArmadaOS. It turns the bottom screen into buttons, a number pad, a trackpad and a keyboard that send ordinary keyboard and mouse input to the game on the top screen.

## Features

- **Pages** of buttons for WoW's default keys: Interface, Target and Utility.
- **Number pad** for action bar 1, with swipes for Shift and Ctrl.
- **Trackpad** and **keyboard**, one tap away.
- **Four themes**: Classic, Charcoal, Dark, and Game Glass over a picture of your choice.
- **Haptics**, a **clock and battery**, and **burn-in protection** for the OLED screen.
- **Remap any button** from Decky, and keep sets of remaps as profiles.
- Runs in **Game Mode** and, optionally, **Desktop Mode**.

## Install

You need an AYN Thor with ArmadaOS and Decky Loader, and SSH access to it (Armada Tools → Remote Access shows its address). On a computer, clone the repository (or download and unzip the latest [release](https://github.com/Zensenshi/JarnGrip/releases/latest)) and run the installer:

```sh
git clone https://github.com/Zensenshi/JarnGrip.git
cd JarnGrip
./scripts/install-from-pc.sh armada@THOR_IP
```

Then open **Steam menu → Decky → JarnGrip** and turn the pad on.

## Using it

| On a number | Sends |
|---|---|
| Tap | the number |
| Swipe up | Shift + number |
| Swipe down | Ctrl + number |
| Swipe left | nothing (cancel) |

The buttons along the top switch pages, open the **trackpad**, the **keyboard** and the **settings** (gear), where you'll find the themes, **Unstick keys** and **Close pad**.

Two tips:

- **Previous enemy opens the Steam menu?** WoW's default for it, Shift+Tab, is also Steam's overlay shortcut. Bind it to Ctrl+Tab in WoW and remap it in Decky.
- **Keys act as if Shift is held?** Tap **Unstick keys** in the settings.

Every button sends one key per press, never a sequence. For emotes, make a WoW macro and put it on an action bar.

More in the [guide](docs/guide.md).

## Uninstall

```sh
./scripts/uninstall-from-pc.sh armada@THOR_IP
```

Your settings stay in `~/.config/jarngrip/` on the Thor.

## Credits

JarnGrip builds on [Ratatoskr](https://github.com/venatrix-ritz/Ratatoskr) by Ven (its input engine, under MIT) and the second-screen pad of [AYN-Thor-WoW-Launcher](https://github.com/wyattabuntjer/AYN-Thor-WoW-Launcher) by wyattabuntjer. Thanks also to [Project Barry](https://github.com/project-barry/barry-launcher), [Armada OS](https://armadaos.dev), [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader), [InputPlumber](https://github.com/ShadowBlip/InputPlumber), and the [Cinzel](https://github.com/NDISCOVER/Cinzel) and [Nunito](https://github.com/googlefonts/nunito) fonts. [NOTICE.md](NOTICE.md) has the details.

## License

Copyright (C) 2026 Zensenshi. [GPL-3.0](LICENSE). The files from Ratatoskr stay under their [MIT license](driver/RATATOSKR-MIT-LICENSE.txt).

An unofficial project, not affiliated with Blizzard, Valve or AYN. World of Warcraft is a trademark of Blizzard Entertainment. Use at your own risk: whether a game allows an input tool is up to its publisher.
