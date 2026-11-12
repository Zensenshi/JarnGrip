# JarnGrip

A touch control pad for the AYN Thor's bottom screen, built for World of Warcraft, Final Fantasy XI and other MMOs. Named after Járngreipr, Thor's iron gloves.

JarnGrip is a [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) plugin for ArmadaOS. It turns the bottom screen into buttons, a number pad, a trackpad and a keyboard that send ordinary keyboard and mouse input to the game on the top screen.

## Features

- **Pages** of buttons for the game's default keys, for **WoW** or **FFXI**, or a **Desktop** profile for the desktop and the web (picked in Decky).
- **Number pad** with swipes: Shift and Ctrl for WoW's action bars, Ctrl and Alt for FFXI's two macro bars.
- **Number pad icons**: put your own pictures on the numbers and their swipes, or let the JarnGrip WoW addon show your action bars' icons and spell names on them.
- **Trackpad** and **keyboard**, one tap away.
- **Four themes**: Classic, Charcoal, Dark, and Game Glass over a picture of your choice.
- **Haptics**, a **clock and battery** that open a **status card** (network, battery and temperatures) with a tap, and **burn-in protection** for the OLED screen.
- **Remap any button** from Decky, and keep sets of remaps as profiles.
- **One press** to open or close it in a game: Home + Start, or the AYN button below the screen.
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

| On a number | WoW | FFXI |
|---|---|---|
| Tap | the number | the number |
| Swipe up | Shift + number | Ctrl + number (upper macro bar) |
| Swipe left | Ctrl + number | Alt + number (lower macro bar) |
| Swipe down | nothing (cancel) | nothing (cancel) |

Press **Home + Start** to open or close the pad at any time, even in a game. Decky can change the shortcut, or let the AYN button below the screen do it. The buttons along the top switch pages, open the **trackpad**, the **keyboard** and the **settings** (gear), where you'll find the themes, **Unstick keys** and **Close pad**.

Two tips:

- **Previous enemy opens the Steam menu?** WoW's default for it, Shift+Tab, is also Steam's overlay shortcut. Bind it to Ctrl+Tab in WoW and remap it in Decky.
- **Keys act as if Shift is held?** Tap **Unstick keys** in the settings.

**Number pad icons** turn the numbers into square keys with your own pictures: one for the tap, and one for each swipe, shown in a square that opens beside the key the way you swipe, and fades after you lift. Copy PNG, JPEG or WebP files into `~/Pictures/JarnGrip/Icons/wow` (or `ffxi`), pick **Icons** under **Number keys show** in Decky, and pick a picture for each key on the full-screen page **Edit icons…** opens. Each profile keeps its own icons. JarnGrip ships no pictures for the numbers: the games' own artwork belongs to their publishers (the guide lists where to find some). In WoW, the small JarnGrip addon (in `wow-addon/`) saves what your action bar keys hold, and the keys show each spell's name, even without icons (the default), or in icon mode its icon where it has no picture of its own: see [the guide](docs/guide.md#your-wow-action-bars-on-the-keys).

In FFXI, swipe a party target (Self, Party 1 to 5) **right** to press Enter after it, which casts a `<stpt>` spell on that member.

**Chat**, the round button on the Utility page, opens a radial of chat channels: slide onto one and lift, or tap **Chat** and then tap a channel, and the chat box opens on that channel with the keyboard ready. The red slice at the bottom cancels. In WoW, which has no key per channel, the pad types the channel's command (`/g `, `/p `, …) but never presses Enter, so nothing is said until you send it. Otherwise every button sends one key per press, never a sequence. For emotes, make a WoW macro and put it on an action bar.

The **Desktop** profile is for everything that is not a game. Its two pages, Edit and Browser, hold the usual editing, navigation, browser and window shortcuts across the whole width, and a **Media** radial. Its keyboard has F1 to F12, Super and the arrow keys above the letters, in place of the small trackpad. On its trackpad, **Back**, **Copy**, **Paste** and **Forward** take the place of Shift, Ctrl and Alt, and you can **pinch** to zoom.

More in the [guide](docs/guide.md).

## Uninstall

**Uninstall JarnGrip** at the bottom of its Decky panel, or from a computer:

```sh
./scripts/uninstall-from-pc.sh armada@THOR_IP
```

Your settings stay in `~/.config/jarngrip/` on the Thor.

The installer adds one file outside the plugin: a polkit rule in `/etc/polkit-1/rules.d/` that lets JarnGrip change what the AYN button does, for **Stop the screenshot**. Uninstalling gives the button its screenshot back; the script also removes the rule, and from Decky the rule stops applying once JarnGrip is gone.

## Credits

JarnGrip builds on [Ratatoskr](https://github.com/venatrix-ritz/Ratatoskr) by Ven (its input engine, under MIT) and the second-screen pad of [AYN-Thor-WoW-Launcher](https://github.com/wyattabuntjer/AYN-Thor-WoW-Launcher) by wyattabuntjer. Thanks also to [Project Barry](https://github.com/project-barry/barry-launcher), [Armada OS](https://armadaos.dev), [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader), [InputPlumber](https://github.com/ShadowBlip/InputPlumber), and the [Cinzel](https://github.com/NDISCOVER/Cinzel) and [Nunito](https://github.com/googlefonts/nunito) fonts. [NOTICE.md](NOTICE.md) has the details.

## License

Copyright (C) 2026 Zensenshi. [GPL-3.0](LICENSE). The files from Ratatoskr stay under their [MIT license](driver/RATATOSKR-MIT-LICENSE.txt).

An unofficial project, not affiliated with Blizzard, Square Enix, Valve or AYN. World of Warcraft is a trademark of Blizzard Entertainment; Final Fantasy XI is a trademark of Square Enix. Use at your own risk: whether a game allows an input tool is up to its publisher.
