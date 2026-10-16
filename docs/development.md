# Developing JarnGrip

## Tests

`python3 tests/test_jarngrip.py` (or `pytest`) runs the tests: the layout, the input rules, the choice of touchscreen and vibration motor, the Decky backend's config handling, and the painter in every theme against a stand-in for cairo. They need no device, GTK or cairo, and run on every push (`.github/workflows/tests.yml`).

## Files

| Path | |
|---|---|
| `main.py`, `dist/index.js`, `plugin.json` | The Decky backend and panel. The backend runs as the `armada` user: `plugin.json` asks for no `root` flag, and a test keeps it that way. |
| `ayn_button.py` | For the backend: "Stop the screenshot", which loads InputPlumber's profile again with the AYN button changed to F24 on its virtual keyboard. |
| `driver/bin/jarngrip.py` | The pad's window, touchscreen reader and lifecycle, in Game Mode or (`--desktop`) Desktop Mode. |
| `driver/bin/pad_model.py` | What is on the screen and what each touch does. No GTK or cairo. |
| `driver/bin/pad_draw.py` | How it looks: themes and painting with cairo. |
| `driver/bin/haptics.py`, `system_status.py`, `touch_device.py` | Vibration, the clock, battery and screens, and finding the touchscreen. |
| `driver/bin/engine.py`, `touch_frames.py`, `burn_in.py`, `driver/debug_codes.py` | From Ratatoskr, under MIT. |
| `driver/fonts/` | Cinzel and Nunito, Bold, under the SIL Open Font License. |
| `driver/bin/ayn_listen.py`, `systemd/jarngrip-ayn.service` | The AYN button listener, a user service while "AYN button" is on. Decky runs the backend without the user's groups, so it cannot read `/dev/input`; the listener can, and writes a byte per press into a FIFO in `/run/user/1000` that the backend reads. |
| `systemd/jarngrip.service` | The Game Mode service. |
| `desktop/` | The Desktop Mode app-menu and autostart entries. |
| `polkit/` | The rule that lets the `armada` user load InputPlumber profiles, for "Stop the screenshot". The installer puts it in `/etc/polkit-1/rules.d/` and the uninstaller removes it. |
| `scripts/` | The install and uninstall scripts. |

[NOTICE.md](../NOTICE.md) says which file came from where; [CHANGELOG.md](../CHANGELOG.md) what changed in each version.

## How it runs

**Installing.** `install-from-pc.sh` packs the repository, copies it over SSH into a fresh private folder on the Thor and runs `install-on-device.sh` there with `sudo`. That script puts the plugin in `/home/armada/homebrew/plugins/jarngrip`, refuses to replace a different plugin, keeps the three newest previous versions in `/home/armada/homebrew/jarngrip-backups` (outside the plugins folder, so Decky does not load them) and restarts Decky. Decky's backend then installs the driver under `~/.local/share/jarngrip` and the user service, and no packages are installed.

**Game Mode.** The pad is `jarngrip.service`, bound to `armada-bottom-gamescope.service`, with `Restart=no` and `Conflicts=` on `touch-master.service` (Ratatoskr) and `armada-bottom-screen.service`. Switching to Desktop Mode stops it with the bottom gamescope session, without any restart loop, and Decky never starts it by itself after a reload ([Ratatoskr issue #34](https://github.com/venatrix-ritz/Ratatoskr/issues/34)). A lock in `/run/user/1000` keeps a Game Mode pad and a Desktop Mode pad from running together.

**Desktop Mode.** `jarngrip.py --desktop` runs as a Wayland app on KDE, fullscreen on the screen shaped like the bottom one (443×386 at scale 2.8 on the Thor), and never takes the keyboard focus.

**Touch.** The pad grabs only an input device whose name contains both `bottom` and `touchscreen` (`bottom_touchscreen` on Armada), never any other, and keeps looking every few seconds until one appears. A button whose finger has reported nothing for 4.5 s is let go, in case the touch controller lost a finger-lift.

**Haptics.** The pad uses the first input device that can play force-feedback effects, gamepads first, skipping any another program has grabbed. On the Thor that is InputPlumber's virtual `Microsoft X-Box 360 pad`, which passes rumble on to the controller's motor (the same buzz as Steam's keyboard); the fainter `qcom-hv-haptics` motor is the fallback. Each buzz is started and stopped explicitly, since InputPlumber does not end an effect by itself.

**Logs.** `DBG-200` names the touchscreen, `DBG-201` means none was found, `DBG-203` that another driver holds it, `DBG-501` logs each touch (on the keyboard without its key or position), `DBG-800` names the vibration device and `DBG-801` says why none could be used.
