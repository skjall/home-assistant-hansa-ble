#!/usr/bin/env python3
"""Print the requirements of the Home Assistant components we pull in.

pytest-homeassistant-custom-component installs Home Assistant, but not what
its bluetooth component needs at runtime. Pinning those by hand means the
numbers drift from the release being tested against, and a dependency bot
keeps proposing bumps that must never be taken on their own. Reading them out
of the installed release removes both problems: they are always exactly right,
and there is nothing left to pin.
"""

from __future__ import annotations

import json
import site
import sys
from pathlib import Path

COMPONENTS = ("bluetooth", "usb")


def main() -> int:
    for directory in site.getsitepackages():
        components = Path(directory) / "homeassistant" / "components"
        if components.is_dir():
            break
    else:
        print("Home Assistant is not installed", file=sys.stderr)
        return 1

    for name in COMPONENTS:
        manifest = components / name / "manifest.json"
        if not manifest.exists():
            print(f"component {name} not found", file=sys.stderr)
            return 1
        for requirement in json.loads(manifest.read_text()).get("requirements", []):
            print(requirement)
    return 0


if __name__ == "__main__":
    sys.exit(main())
