# JarnGrip guide

## The pad

- **Pages**: Interface, Target and Utility, on the left half, send WoW's default keys. A page button is a real key: it is held while your finger is down, and several can be held at once.
- **Number pad**, on the right half: action bar 1. A number is sent when your finger lifts, so a swipe can change it: **up** adds Shift, **down** adds Ctrl, **left** cancels, and **right** sends the plain number. A fan opens in the swipe's direction and names what lifting will send. Bind action bars 2 and 3 to Shift- and Ctrl-number in WoW to reach them this way.
- **Trackpad** (header button): move, tap to click, two fingers to scroll, a scroll strip along the right edge, and **Left click** / **Right click** buttons that stay pressed while held, so they drag and turn the camera. Double-tap a click button to keep it held. **Shift, Ctrl and Alt** arm a modifier for the next click; a double tap locks one until you tap it again.
- **Keyboard** (header button): letters, digits, one-shot Shift and Caps, and a `?123` page with symbols and arrow keys, under a small trackpad. A held key shows its character above your thumb.
- **Settings** (gear button): the theme, which touchscreen and vibration motor the pad uses, **Unstick keys**, and **Close pad**, which gives the bottom screen back without going through Decky.

## The Decky panel

- **Shortcut**: **Home + Start** opens or closes the pad from anywhere in Game Mode, mid-game included, without opening Decky. A toast says which. **Change shortcut** records the next button or buttons you press instead, such as the AYN button below the screen; **Back to Home + Start** undoes it. Turn the shortcut off here if a game needs that combination.
- **AYN button**: the button below the screen opens or closes the pad too. Steam still takes a screenshot each time unless you also turn on **Stop the screenshot**. Until then, **Home + R1** opens and closes the pad as well, because that is what the AYN button sends when InputPlumber emulates a Steam Deck controller.
- **Stop the screenshot**: the AYN button sends F24, a key nothing uses, instead of the screenshot. JarnGrip does this by loading InputPlumber's profile again with that one button changed; no file changes. It stays until you turn it off or uninstall JarnGrip: InputPlumber forgets it when it restarts, and JarnGrip applies it again each time it starts.
- **Theme**, **haptics** strength, **burn-in protection**, a **24-hour clock**, and **Start with Desktop Mode**.
- **Remap a control**: pick a control, a key and any of **With Ctrl / Shift / Alt**, then save. **Reset to default** puts it back.
- **Profiles**: saved sets of remaps. Load one, save to it, save as a new profile, or delete one.
- **Trackpad sensitivity**, **Stop and restore screen services**, and **Uninstall JarnGrip**, which uses Decky's own uninstall: it stops the pad, gives the bottom screen and the AYN button back, and removes JarnGrip, keeping your settings and profiles.

While the pad runs, it stops Ratatoskr or Armada's own bottom-screen service, and starts it again when you stop the pad. Don't run two bottom-screen drivers at once.

## Game Glass pictures

Put PNG, JPEG or WebP files in `~/Pictures/JarnGrip` on the Thor (for example with `scp`), choose **Game Glass** in Decky and pick a picture. **Glass blur** sets how strongly it is blurred. Without a picture, the theme uses a built-in color wash.

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
| `bindings` | `{control: key}` | `"slot_1": "ctrl+59"` sends Ctrl+F1; `"previous_enemy": "33"` sends a plain F. Keys are [Linux key codes](https://github.com/torvalds/linux/blob/master/include/uapi/linux/input-event-codes.h). A bare number replaces the key but keeps the button's own Shift or Alt. Controls are the page buttons (`character`, `quest_log`, `previous_enemy`, …) and `slot_1` to `slot_12`. |
| `theme` | `classic`, `charcoal`, `dark`, `glass` | |
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
