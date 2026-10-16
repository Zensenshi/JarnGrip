# SPDX-License-Identifier: GPL-3.0-only
"""For the Decky backend: "Stop the screenshot" on the AYN button below the Thor's screen.

InputPlumber, which owns the Thor's controls, turns the button (KEY_F24 from gpio-keys-ayn) into its QuickAccess2
button, and its stock profile maps that to a gamepad Screenshot button, which Steam takes a screenshot on. Stopping the
screenshot loads the profile InputPlumber already has again, with that one mapping changed: QuickAccess2 becomes KEY_F24
on InputPlumber's own virtual keyboard, which nothing else uses. No file changes. InputPlumber loads its stock profile
again whenever it restarts, and the backend applies the change again while its setting is on. Loading a profile needs
the polkit rule the installer adds (polkit/49-jarngrip-inputplumber.rules).

Hearing the presses is driver/bin/ayn_listen.py's job.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

SERVICE = "org.shadowblip.InputPlumber"
COMPOSITE = "org.shadowblip.Input.CompositeDevice"
TARGET = "org.shadowblip.Input.Target"
STOCK_PROFILE = "/usr/share/inputplumber/profiles/default.yaml"
MARK = " + JarnGrip"  # ends the name of a profile this module loaded
MAPPING = """- name: AYN button (JarnGrip)
  source_event:
    gamepad:
      button: QuickAccess2
  target_events:
  - keyboard: KeyF24"""


# ---------------------------------------------------------------------------------------------- the profile

def without_screenshot(profile: str, targets: list) -> str:
    """The profile with QuickAccess2 sending KEY_F24 on a virtual keyboard instead of whatever it sent, and that
    keyboard added to its target devices. Works on the YAML InputPlumber writes itself (GetProfileYaml), and gives the
    same result when applied twice."""
    lines = profile.splitlines()
    if not any(line.strip() == "kind: DeviceProfile" for line in lines):
        raise ValueError("not an InputPlumber device profile")
    start = next((i for i, line in enumerate(lines) if line.rstrip() in ("mapping:", "mapping: []")), None)
    if start is None:
        raise ValueError("the profile has no mapping list")
    end = start + 1
    while end < len(lines) and lines[end].startswith(("- ", " ")):
        end += 1
    items: list = []
    for line in lines[start + 1:end]:
        if line.startswith("- "):
            items.append([])
        if items:
            items[-1].append(line)
    kept = ["\n".join(item) for item in items if not _maps_quickaccess2("\n".join(item))]

    head, tail = _without_key(lines[:start], "target_devices"), _without_key(lines[end:], "target_devices")
    for i, line in enumerate(head):
        if line.startswith("name:"):
            name = line[5:].strip()
            if name[:1] in "'\"" and name[-1:] == name[:1]:
                name = name[1:-1]
            head[i] = "name: " + json.dumps(name if name.endswith(MARK) else name + MARK)
    devices = list(dict.fromkeys([*targets, "keyboard"]))
    return "\n".join([*head, "target_devices:", *(f"- {t}" for t in devices), "mapping:", *kept, MAPPING, *tail]) + "\n"


def _maps_quickaccess2(item: str) -> bool:
    return re.search(r"source_event:\s*\n\s+gamepad:\s*\n\s+button:\s*QuickAccess2\s*$", item, re.MULTILINE) is not None


def _without_key(lines: list, key: str) -> list:
    """The lines without a top-level key and the list or block under it."""
    out, skipping = [], False
    for line in lines:
        if line.startswith(f"{key}:"):
            skipping = True
            continue
        if skipping and line.startswith(("- ", " ")):
            continue
        skipping = False
        out.append(line)
    return out


# ---------------------------------------------------------------------------------------------- InputPlumber

class BusError(Exception):
    pass


def _busctl(*args: str):
    """Run busctl on the system bus and return the call's data. Never asks for a password: with no polkit rule, a
    refused call fails at once."""
    try:
        done = subprocess.run(["busctl", "--system", "--json=short", "--allow-interactive-authorization=no", *args],
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
    except (OSError, subprocess.SubprocessError) as err:
        raise BusError(str(err)) from err
    if done.returncode != 0:
        raise BusError(done.stderr.strip() or f"busctl exited with {done.returncode}")
    return json.loads(done.stdout)["data"] if done.stdout.strip() else None


def _get(path: str, interface: str, prop: str):
    return _busctl("get-property", SERVICE, path, interface, prop)


def _call(path: str, method: str, *args: str):
    return _busctl("call", SERVICE, path, COMPOSITE, method, *args)


_known: list = []  # [(D-Bus path, name)] of the AYN devices, kept until InputPlumber fails a call


def _ayn_devices() -> list:
    """[(D-Bus path, name)] of InputPlumber's composite devices for AYN controls (one, on a Thor). Looked up once, not
    on every check: the backend checks every few seconds."""
    global _known
    if not _known:
        try:
            done = subprocess.run(["busctl", "--system", "--list", "tree", SERVICE], text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, timeout=8)
        except (OSError, subprocess.SubprocessError) as err:
            raise BusError(str(err)) from err
        paths = [p.strip() for p in done.stdout.split() if re.search(r"/CompositeDevice\d+$", p.strip())]
        _known = [(p, name) for p in paths if (name := str(_get(p, COMPOSITE, "Name"))).startswith("AYN")]
    return _known


def sync(wanted: bool, state_file: Path) -> str:
    """Make the AYN button's screenshot match the setting: stopped (wanted) or back. Returns "" or what went wrong.

    The profile in use before the first change is kept in state_file, by device name, so that turning the setting off
    loads that profile again rather than the stock one."""
    try:
        saved = json.loads(state_file.read_text())
    except (OSError, ValueError):
        saved = {}
    if not isinstance(saved, dict):
        saved = {}
    if not wanted and not saved:
        return ""  # never changed anything: nothing to put back, and no need to ask InputPlumber
    global _known
    try:
        for path, device in _ayn_devices():
            ours = str(_get(path, COMPOSITE, "ProfileName")).endswith(MARK)
            if wanted:
                # Target paths end in their kind and a number (".../target/keyboard0"): no need to ask each one.
                target_paths = [str(t) for t in _get(path, COMPOSITE, "TargetDevices") or []]
                if ours and any(t.rsplit("/", 1)[-1].startswith("keyboard") for t in target_paths):
                    continue  # the usual case, every few seconds: two calls, and nothing to do
                targets = [str(_get(t, TARGET, "DeviceType")) for t in target_paths]
                profile = _call(path, "GetProfileYaml")[0]
                if not ours:
                    saved[device] = {"path": str(_get(path, COMPOSITE, "ProfilePath") or ""), "yaml": profile}
                    _write_state(state_file, saved)
                _call(path, "LoadProfileFromYaml", "s", without_screenshot(profile, [t for t in targets if t]))
            else:
                before = saved.pop(device, None) or {}
                if ours:
                    if before.get("path") and os.path.isfile(before["path"]):
                        _call(path, "LoadProfilePath", "s", before["path"])
                    elif before.get("yaml"):
                        _call(path, "LoadProfileFromYaml", "s", before["yaml"])
                    else:
                        _call(path, "LoadProfilePath", "s", STOCK_PROFILE)
                _write_state(state_file, saved)
    except BusError as err:
        _known = []  # InputPlumber may have restarted with new paths: look them up again next time
        text = str(err)
        if "denied" in text.lower() or "authoriz" in text.lower():
            return "InputPlumber refused to change the button. Reinstall JarnGrip to allow it."
        return f"Could not change the AYN button: {text}"
    except (ValueError, LookupError, TypeError) as err:
        return f"Could not change the AYN button: {err}"
    return ""


def _write_state(state_file: Path, saved: dict) -> None:
    if not saved:
        state_file.unlink(missing_ok=True)
        return
    state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(saved))
    os.replace(tmp, state_file)
