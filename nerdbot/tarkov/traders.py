"""Trader restock times from the json.tarkov.dev ``{mode}/traders`` feed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import orjson


@dataclass(slots=True)
class Restock:
    name: str
    slug: str
    at: datetime | None  # next restock, as reported by tarkov.dev
    image: str | None = None


def _ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_restocks(traders_raw: bytes, names_raw: bytes) -> list[Restock]:
    """Restock times for traders that sell things, soonest first.

    Single-level traders (Lightkeeper, BTR Driver, Taran and the like) are skipped: they
    don't have a regular stock to wait for.
    """
    traders = orjson.loads(traders_raw)["data"]
    names = orjson.loads(names_raw)["data"]
    out = []
    for t in traders.values():
        if len(t.get("levels") or ()) < 2:
            continue
        slug = t.get("normalizedName") or ""
        out.append(
            Restock(
                name=names.get(t.get("name"), slug.replace("-", " ").title()),
                slug=slug,
                at=_ts(t.get("resetTime")),
                image=t.get("imageLink"),
            )
        )
    out.sort(key=lambda r: (r.at is None, r.at or datetime.max, r.name))
    return out
