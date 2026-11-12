#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Make icon-names.csv, the list that lets JarnGrip find your picture for an icon the WoW addon saved.

WoW names each icon by a number (a file id); the pictures exported from the game are named for the icon's file
(spell_nature_lightning.png). The community listfile (https://github.com/wowdev/wow-listfile) pairs the two for every
file in the game. This keeps only the icons, a small file, which goes in ~/Pictures/JarnGrip/Icons/wow on the Thor:

    python3 scripts/wow-icon-names.py                      # downloads the listfile
    python3 scripts/wow-icon-names.py community-listfile.csv   # or reads one you have
    scp icon-names.csv armada@<thor-ip>:Pictures/JarnGrip/Icons/wow/
"""
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "driver" / "bin"))
from wow_bars import icon_line  # noqa: E402 - the same lines the pad reads

LISTFILE = "https://github.com/wowdev/wow-listfile/releases/latest/download/community-listfile.csv"


def icons(lines):
    for line in lines:
        found = icon_line(line)
        if found:
            yield f"{found[0]};{found[1]}\n"


def main() -> int:
    out = "icon-names.csv"
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
            found = list(icons(f))
    else:
        print(f"Downloading {LISTFILE} (large: it lists every file in the game)...", file=sys.stderr)
        with urllib.request.urlopen(LISTFILE) as response:
            found = list(icons(line.decode("utf-8", "replace") for line in response))
    if not found:
        print("No icons found in that listfile.", file=sys.stderr)
        return 1
    with open(out, "w", encoding="utf-8") as f:
        f.writelines(found)
    print(f"Wrote {len(found)} icons to {out}. Copy it to ~/Pictures/JarnGrip/Icons/wow on the Thor.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
