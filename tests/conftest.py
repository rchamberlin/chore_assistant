"""Test harness that makes the integration's pure logic importable without a
full Home Assistant install.

`models.py` and `const.py` touch only a tiny slice of Home Assistant
(`homeassistant.util.dt` and `homeassistant.const.Platform`). We stub exactly
that slice, then expose the integration package under the import name ``ca``
WITHOUT executing its `__init__.py` (which pulls in the full HA runtime).

The coordinator and entity platforms are deliberately out of scope here: they
require Home Assistant's own pytest fixtures
(`pytest-homeassistant-custom-component`).
"""

from __future__ import annotations

import sys
import types
from datetime import datetime, timezone
from pathlib import Path

# A fixed, deterministic default timezone for the schedule math.
TEST_TZ = timezone.utc


def _install_ha_stubs() -> None:
    ha = types.ModuleType("homeassistant")
    ha.__path__ = []  # mark as package

    const = types.ModuleType("homeassistant.const")

    class Platform:
        TODO = "todo"
        CALENDAR = "calendar"
        SENSOR = "sensor"

    const.Platform = Platform

    util = types.ModuleType("homeassistant.util")
    util.__path__ = []

    dt = types.ModuleType("homeassistant.util.dt")
    dt.DEFAULT_TIME_ZONE = TEST_TZ
    dt.now = lambda: datetime.now(TEST_TZ)

    def parse_datetime(value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    dt.parse_datetime = parse_datetime

    # Wire submodules as attributes so `from homeassistant.util import dt`
    # and `from homeassistant.const import Platform` resolve.
    ha.const = const
    ha.util = util
    util.dt = dt

    sys.modules.setdefault("homeassistant", ha)
    sys.modules.setdefault("homeassistant.const", const)
    sys.modules.setdefault("homeassistant.util", util)
    sys.modules.setdefault("homeassistant.util.dt", dt)


def _expose_package() -> None:
    pkg_dir = Path(__file__).resolve().parents[1] / "custom_components" / "chore_assistant"
    pkg = types.ModuleType("ca")
    pkg.__path__ = [str(pkg_dir)]
    sys.modules["ca"] = pkg


_install_ha_stubs()
_expose_package()
