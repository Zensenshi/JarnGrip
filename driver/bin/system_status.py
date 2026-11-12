# SPDX-License-Identifier: GPL-3.0-only
"""Facts about the device the pad runs on: the clock and battery in its header, the network, battery and temperatures
on the status card a tap on them opens, and which screen is the bottom one. No GTK in here, so it is tested anywhere."""
from __future__ import annotations

import glob
import os
import socket
import subprocess
import time
from collections import deque

# What NetworkManager's own connectivity check says (nmcli networking connectivity), as the status card puts it.
INTERNET = {"full": "Connected", "limited": "Limited", "portal": "Sign-in needed", "none": "None",
            "unknown": "Not checked"}


def clock_text(clock_24h: bool = False, now: float | None = None) -> str:
    stamp = time.localtime(now)
    return time.strftime("%H:%M", stamp) if clock_24h else time.strftime("%I:%M", stamp).lstrip("0")


def read_battery(root: str = "/sys/class/power_supply") -> tuple:
    """(percent, charging) of the first battery, or (None, False) if there is none."""
    for device in sorted(glob.glob(os.path.join(root, "*"))):
        try:
            with open(os.path.join(device, "type"), encoding="utf-8") as f:
                if f.read().strip() != "Battery":
                    continue
            with open(os.path.join(device, "capacity"), encoding="utf-8") as f:
                percent = int(f.read().strip())
            try:
                with open(os.path.join(device, "status"), encoding="utf-8") as f:
                    status = f.read().strip()
            except OSError:
                status = ""
        except (OSError, ValueError):
            continue
        return max(0, min(100, percent)), status in ("Charging", "Full")
    return None, False


def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def _int(path: str) -> int | None:
    try:
        return int(_read(path) or "")
    except ValueError:
        return None


def read_battery_details(root: str = "/sys/class/power_supply") -> dict | None:
    """The first battery's details for the status card, or None if there is none: its status ("Charging",
    "Discharging", "Full", ...), percent, what it holds now and full and when new, the rate it charges or drains at
    (current against charge, or power against energy, whichever the driver gives: the same units, so they divide into
    hours), the watts, its temperature in degrees, its cycles and the driver's word for its health. A value the driver
    does not give is None."""
    for device in sorted(glob.glob(os.path.join(root, "*"))):
        if _read(os.path.join(device, "type")) != "Battery":
            continue
        value = lambda name: _int(os.path.join(device, name))  # noqa: E731
        percent = value("capacity")
        if percent is None:
            continue
        if value("charge_now") is not None:
            now, full, design, rate = value("charge_now"), value("charge_full"), value("charge_full_design"), \
                value("current_now")
            volts = value("voltage_now")
            # power_now is not to be trusted where current is given: the Thor's says 40 W at 2 W.
            watts = abs(rate * volts) / 1e12 if rate is not None and volts is not None else None
        else:
            now, full, design, rate = value("energy_now"), value("energy_full"), value("energy_full_design"), \
                value("power_now")
            watts = abs(rate) / 1e6 if rate is not None else None
        temp = value("temp")
        return {"status": _read(os.path.join(device, "status")) or "", "percent": max(0, min(100, percent)),
                "now": now, "full": full, "design": design, "rate": abs(rate) if rate is not None else None,
                "watts": watts, "temp": temp / 10 if temp is not None else None, "cycles": value("cycle_count"),
                "health": _read(os.path.join(device, "health"))}
    return None


class BatteryRate:
    """The battery's charge or drain rate, averaged over the last WINDOW_S seconds it has kept one status: a single
    reading jumps with every load, so the time it gives would too. Fed once a second, whether the card is open or not,
    so that its estimate is ready when the card opens."""
    WINDOW_S = 60.0
    MIN_SAMPLES = 3

    def __init__(self) -> None:
        self.samples: deque = deque()
        self.status: str | None = None

    def add(self, details: dict | None, now: float) -> None:
        if not details or details.get("rate") is None:
            return
        if details["status"] != self.status:  # plugged in or out: the old rate says nothing about the new one
            self.samples.clear()
            self.status = details["status"]
        self.samples.append((now, details["rate"]))
        while now - self.samples[0][0] > self.WINDOW_S:
            self.samples.popleft()

    def hours(self, details: dict | None) -> float | None:
        """Hours until empty while it drains, until full while it charges; None when there is no telling yet."""
        if not details or len(self.samples) < self.MIN_SAMPLES or details.get("now") is None:
            return None
        rate = sum(r for _, r in self.samples) / len(self.samples)
        if rate <= 0:
            return None
        if details["status"] == "Discharging":
            return details["now"] / rate
        if details["status"] == "Charging" and details.get("full") is not None:
            return max(0, details["full"] - details["now"]) / rate
        return None


def read_temperatures(root: str = "/sys/class/thermal") -> dict:
    """The hottest CPU and GPU sensor and the battery's, in degrees: {"CPU": 44.2, "GPU": 41.4, "Battery": 30.0}, for
    those the device has. The Thor has a sensor per core and cluster (cpu7-top-thermal, cpuss0-thermal,
    gpuss-1-thermal); a PC reports x86_pkg_temp."""
    found: dict = {}
    for zone in sorted(glob.glob(os.path.join(root, "thermal_zone*"))):
        kind, temp = (_read(os.path.join(zone, "type")) or "").lower(), _int(os.path.join(zone, "temp"))
        if temp is None or not -30_000 < temp < 150_000:
            continue
        group = "CPU" if kind.startswith("cpu") or kind == "x86_pkg_temp" else "GPU" if kind.startswith("gpu") \
            else "Battery" if kind.startswith("batt") else None
        if group:
            found[group] = max(found.get(group, -1000.0), temp / 1000)
    return found


def read_fan(root: str = "/sys/class/hwmon") -> int | None:
    """The fan's speed in revolutions a minute, or None for a device without one."""
    for path in sorted(glob.glob(os.path.join(root, "hwmon*", "fan*_input"))):
        rpm = _int(path)
        if rpm is not None:
            return rpm
    return None


def _terse(line: str) -> list:
    """The fields of a line of nmcli -t, which escapes a : or \\ in a value with a \\ (an SSID can hold either)."""
    fields, field, escaped = [], "", False
    for ch in line:
        if escaped:
            field, escaped = field + ch, False
        elif ch == "\\":
            escaped = True
        elif ch == ":":
            fields.append(field)
            field = ""
        else:
            field += ch
    return fields + [field]


def _nmcli(args: list, run) -> list | None:
    """The lines nmcli prints for args, or None if it is missing, fails or hangs."""
    try:
        done = run(["nmcli", "-t", *args], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.splitlines() if done.returncode == 0 else None


def _local_ip() -> str:
    """The address the device would send from, without nmcli: connecting a UDP socket only picks a route, it sends
    nothing."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # TEST-NET-1, never a real host
            return s.getsockname()[0]
    except OSError:
        return ""


def band_of(mhz: int) -> str:
    return "2.4 GHz" if mhz < 3000 else "5 GHz" if mhz < 5925 else "6 GHz"


def read_network(run=subprocess.run, local_ip=_local_ip) -> dict:
    """The network the device is on, as NetworkManager sees it: {"kind": "wifi", "ethernet" or "" when offline,
    "device", "name" (the Wi-Fi's SSID), "signal" (percent), "mhz", "rate" ("130 Mbit/s"), "ip", "internet"}. It
    sends nothing itself: the internet check is NetworkManager's own, from its last look. Slow (nmcli takes a moment):
    call it off the drawing thread."""
    devices = _nmcli(["-f", "DEVICE,TYPE,STATE", "device"], run)
    if devices is None:  # no NetworkManager: the address is still worth showing
        ip = local_ip()
        return {"kind": "other" if ip else "", "device": "", "ip": ip, "internet": ""}
    up = [f for f in map(_terse, devices) if len(f) >= 3 and f[2] == "connected" and f[1] in ("wifi", "ethernet")]
    if not up:
        return {"kind": "", "device": "", "ip": "", "internet": "none"}
    device, kind = up[0][0], up[0][1]
    found = {"kind": kind, "device": device, "name": "", "signal": None, "mhz": None, "rate": "", "ip": "",
             "internet": ""}
    if kind == "wifi":
        # --rescan no: the list NetworkManager already has. A scan would take seconds, and stall the Wi-Fi meanwhile.
        for f in map(_terse, _nmcli(["-f", "ACTIVE,SSID,SIGNAL,FREQ,RATE", "device", "wifi", "list", "--rescan", "no"],
                                    run) or []):
            if len(f) >= 5 and f[0] == "yes":
                found["name"], found["rate"] = f[1], f[4]
                found["signal"] = int(f[2]) if f[2].isdigit() else None
                mhz = f[3].split()[0] if f[3] else ""
                found["mhz"] = int(mhz) if mhz.isdigit() else None
                break
    for f in map(_terse, _nmcli(["-f", "IP4.ADDRESS", "device", "show", device], run) or []):
        if len(f) >= 2 and f[0].startswith("IP4.ADDRESS") and f[1]:
            found["ip"] = f[1].split("/")[0]
            break
    found["ip"] = found["ip"] or local_ip()
    state = _nmcli(["networking", "connectivity"], run)
    found["internet"] = state[0].strip() if state else ""
    return found


def _span(hours: float) -> str:
    minutes = round(hours * 60)
    if minutes < 1:
        return "under a minute"
    return f"{minutes // 60} h {minutes % 60:02d} min" if minutes >= 60 else f"{minutes} min"


def _degrees(value: float | None) -> str:
    return f"{value:.0f} °C" if value is not None else "–"


def card_sections(network: dict | None, battery: dict | None, hours: float | None, temps: dict,
                  fan: int | None) -> list:
    """What the status card shows: [(heading, [(label, value), ...]), ...], one column each. network is None while it
    is still being read."""
    if network is None:
        net = [("Status", "Looking…")]
    elif not network.get("kind"):
        net = [("Status", "Offline")]
    else:
        if network["kind"] == "wifi":
            signal = network.get("signal")
            net = [("Wi-Fi", network.get("name") or "Hidden network")]
            if signal is not None:
                net.append(("Signal", f"{signal}% · " + ("Strong" if signal >= 67 else "Fair" if signal >= 34
                                                           else "Weak")))
            band = [band_of(network["mhz"])] if network.get("mhz") else []
            net.append(("Band", " · ".join(band + ([network["rate"]] if network.get("rate") else [])) or "–"))
        elif network["kind"] == "ethernet":
            net = [("Wired", network.get("device") or "Connected")]
        else:
            net = [("Status", "Connected")]
        net.append(("IP address", network.get("ip") or "None yet"))
        if network.get("internet"):
            net.append(("Internet", INTERNET.get(network["internet"], network["internet"].capitalize())))
    sections = [("Network", net)]

    if battery:
        status, percent = battery["status"], battery["percent"]
        state = {"Charging": "charging", "Discharging": "on battery", "Full": "full",
                 "Not charging": "not charging"}.get(status, status.lower() or "")
        rows = [("Charge", f"{percent}%" + (f" · {state}" if state else ""))]
        if status == "Charging" and percent >= 100:
            rows.append(("Until full", "Full"))
        elif status in ("Charging", "Discharging"):
            rows.append(("Until full" if status == "Charging" else "Time left",
                         _span(hours) if hours is not None else "Measuring…"))
        if battery.get("watts") is not None and status in ("Charging", "Discharging"):
            rows.append(("Power", f"{'Charging' if status == 'Charging' else 'Using'} {battery['watts']:.1f} W"))
        health = [battery["health"]] if battery.get("health") else []
        if not health and battery.get("full") and battery.get("design"):
            health = [f"{round(100 * battery['full'] / battery['design'])}% of new"]
        cycles = [f"{battery['cycles']} cycles"] if battery.get("cycles") is not None else []
        if health or cycles:
            rows.append(("Health", " · ".join(health + cycles)))
        sections.append(("Battery", rows))

    heat = [(name, _degrees(temps.get(name))) for name in ("CPU", "GPU") if name in temps]
    battery_temp = battery.get("temp") if battery else None
    battery_temp = battery_temp if battery_temp is not None else temps.get("Battery")
    if battery_temp is not None:
        heat.append(("Battery", _degrees(battery_temp)))
    if fan is not None:
        heat.append(("Fan", f"{fan} rpm" if fan else "Off"))
    if heat:
        sections.append(("Temperatures", heat))
    return sections


def bottom_screen(sizes: list, width: float = 1240, height: float = 1080) -> int | None:
    """Of the desktop's screens, given as (width, height) in any unit, the index of the bottom one: the one shaped most
    like it. In Desktop Mode the top screen is 16:9 and the bottom one about 8:7, so the shape tells them apart
    whatever scale the desktop gives each."""
    if not sizes:
        return None
    return min(range(len(sizes)), key=lambda i: abs(sizes[i][0] / max(sizes[i][1], 1) - width / height))
