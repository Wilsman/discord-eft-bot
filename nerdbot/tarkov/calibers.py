from __future__ import annotations

import re

_NAMES = {
    "Caliber1143x23ACP": ".45 ACP",
    "Caliber127x33": ".50 AE",
    "Caliber127x55": "12.7x55mm",
    "Caliber127x99": ".50 BMG",
    "Caliber12g": "12/70",
    "Caliber20g": "20/70",
    "Caliber20x1mm": "20x1mm",
    "Caliber23x75": "23x75mm",
    "Caliber26x75": "26x75mm",
    "Caliber366TKM": ".366 TKM",
    "Caliber40mmRU": "40mm VOG",
    "Caliber40x46": "40x46mm",
    "Caliber46x30": "4.6x30mm",
    "Caliber545x39": "5.45x39mm",
    "Caliber556x45NATO": "5.56x45mm",
    "Caliber57x28": "5.7x28mm",
    "Caliber58x42": "5.8x42mm",
    "Caliber68x51": "6.8x51mm",
    "Caliber762x25TT": "7.62x25mm TT",
    "Caliber762x35": ".300 Blackout",
    "Caliber762x39": "7.62x39mm",
    "Caliber762x51": "7.62x51mm",
    "Caliber762x54R": "7.62x54mmR",
    "Caliber784x49": ".308 ME",
    "Caliber86x70": ".338 Lapua",
    "Caliber93x64": "9.3x64mm",
    "Caliber9x18PM": "9x18mm PM",
    "Caliber9x19PARA": "9x19mm",
    "Caliber9x21": "9x21mm",
    "Caliber9x33R": ".357 Magnum",
    "Caliber9x39": "9x39mm",
}


def caliber_name(raw: str | None) -> str:
    """Human name for a tarkov.dev caliber id like ``Caliber556x45NATO``."""
    if not raw:
        return "Unknown"
    if raw in _NAMES:
        return _NAMES[raw]
    # Unknown future calibers: "Caliber762x51" -> "762x51" is still readable.
    return re.sub(r"^Caliber", "", raw)
