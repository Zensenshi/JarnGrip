# JarnGrip guide

## The pad

- **Pages**: Interface, Target and Utility, on the left half, send WoW's default keys. A page button is a real key: it is held while your finger is down, and several can be held at once.
- **Number pad**, on the right half: action bar 1. A number is sent when your finger lifts, so a swipe can change it: **up** adds Shift, **down** adds Ctrl, **left** cancels, and **right** sends the plain number. A fan opens in the swipe's direction and names what lifting will send. Bind action bars 2 and 3 to Shift- and Ctrl-number in WoW to reach them this way.
- **Trackpad** (header button): move, tap to click, two fingers to scroll, a scroll strip along the right edge, and **Left click** / **Right click** buttons that stay pressed while held, so they drag and turn the camera. Double-tap a click button to keep it held. **Shift, Ctrl and Alt** arm a modifier for the next click; a double tap locks one until you tap it again.
- **Keyboard** (header button): letters, digits, one-shot Shift and Caps, and a `?123` page with symbols and arrow keys, under a small trackpad. A held key shows its character above your thumb.
- **Settings** (gear button): the theme, which touchscreen and vibration motor the pad uses, **Unstick keys**, and **Close pad**, which gives the bottom screen back without going through Decky.

## The Decky panel

- **Theme**, **haptics** strength, **burn-in protection**, a **24-hour clock**, and **Also run in Desktop Mode**.
- **Remap a control**: pick a control, a key and any of **With Ctrl / Shift / Alt**, then save. **Reset to default** puts it back.
- **Profiles**: saved sets of remaps. Load one, save to it, save as a new profile, or delete one.
- **Trackpad sensitivity**, and **Stop and restore screen services**.

While the pad runs, it stops Ratatoskr or Armada's own bottom-screen service, and starts it again when you stop the pad. Don't run two bottom-screen drivers at once.

## Game Glass pictures

Put PNG, JPEG or WebP files in `~/Pictures/JarnGrip` on the Thor (for example with `scp`), choose **Game Glass** in Decky and pick a picture. **Glass blur** sets how strongly it is blurred. Without a picture, the theme uses a built-in color wash.

## Desktop Mode

Turn on **Also run in Desktop Mode** in Decky, or start **JarnGrip** from the desktop's app menu. The pad opens fullscreen on the bottom screen without taking the keyboard focus from your game. **Close pad** gives the bottom screen back to the desktop.

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
