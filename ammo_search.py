from typing import Dict, Any, Optional, Tuple
import aiohttp
from datetime import datetime, timezone as tz
import os
import json
import discord

# Optional fuzzy match: prefer fuzzywuzzy if installed; fallback to difflib
try:
    from fuzzywuzzy import process as fw_process  # type: ignore
except Exception:  # ModuleNotFoundError or others
    fw_process = None
    import difflib

# Cache configuration (mirrors price_search.py approach)
CACHE_FILE = os.path.join(os.path.dirname(__file__), "ammo_cache.json")
CACHE_TTL_SECONDS = 600  # 10 minutes


async def fetch_ammo_data() -> Optional[Dict[str, Any]]:
    """Fetch ammo from GraphQL API with on-disk caching.

    Returns a dict: { "ammo": [...], "fetchedAt": iso_string }
    """
    # 1) Serve fresh cache when available
    try:
        if os.path.exists(CACHE_FILE):
            mtime = os.path.getmtime(CACHE_FILE)
            if (datetime.now(tz.utc).timestamp() - mtime) < CACHE_TTL_SECONDS:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
    except Exception as e:
        print(f"[ammo] Cache read error: {e}")

    # 2) Fetch from GraphQL and rebuild cache
    url = "https://api.tarkov.dev/graphql"
    query = """
    query MyQuery {
      ammo {
        item {
          name
          normalizedName
          shortName
        }
        ammoType
        armorDamage
        caliber
        damage
        penetrationChance
        penetrationPower
        projectileCount
        tracer
        tracerColor
      }
    }
    """

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"query": query}) as response:
                if response.status != 200:
                    print(f"[ammo] GraphQL error: HTTP {response.status}")
                    return None
                payload = await response.json()

        data = payload.get("data", {})
        ammo_list = data.get("ammo", [])

        result = {
            "ammo": ammo_list,
            "fetchedAt": datetime.now(tz.utc).isoformat(),
        }

        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False)
        except Exception as e:
            print(f"[ammo] Cache write error: {e}")

        return result
    except Exception as e:
        print(f"[ammo] Error fetching ammo data: {e}")
        return None


def _build_match_pools(ammo_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    names: Dict[str, Any] = {}
    shorts: Dict[str, Any] = {}
    norms: Dict[str, Any] = {}

    for entry in ammo_data.get("ammo", []) or []:
        item = entry.get("item") or {}
        name = (item.get("name") or "").strip()
        short = (item.get("shortName") or "").strip()
        norm = (item.get("normalizedName") or "").strip()
        if name:
            names[name.lower()] = entry
        if short:
            shorts[short.lower()] = entry
        if norm:
            norms[norm.lower()] = entry
    return names, shorts, norms


def find_ammo(ammo_data: Dict[str, Any], search_term: str) -> Optional[Dict[str, Any]]:
    """Fuzzy find an ammo entry by item name, shortName, or normalizedName."""
    if not ammo_data or "ammo" not in ammo_data:
        return None

    names, shorts, norms = _build_match_pools(ammo_data)
    query = search_term.lower().strip()

    def best_match_dict(query_str: str, pool: Dict[str, Any]):
        if fw_process is not None:
            return fw_process.extractOne(query_str, list(pool.keys()))  # (choice, score)
        # difflib fallback
        if not pool:
            return None
        choices = list(pool.keys())
        best = None
        best_score = -1.0
        for choice in choices:
            score = difflib.SequenceMatcher(a=query_str, b=choice).ratio()
            if score > best_score:
                best_score = score
                best = choice
        return (best, int(round(best_score * 100))) if best is not None else None

    candidates = []
    for pool in (names, shorts, norms):
        match = best_match_dict(query, pool)
        if match and match[0] in pool:
            candidates.append((pool[match[0]], match[1]))

    if not candidates:
        return None

    # Pick highest score above threshold
    best_entry, best_score = max(candidates, key=lambda t: t[1])
    return best_entry if best_score >= 80 else None


def _pen_color(pen: Optional[int]) -> int:
    if isinstance(pen, int):
        if pen >= 50:
            return 0xFF0000  # red
        if pen >= 30:
            return 0xFFA500  # orange
        if pen >= 20:
            return 0xFFFF00  # yellow
    return 0x00FF00  # green


def _format_pct(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    try:
        val = float(v)
        if 0 < val <= 1:
            val *= 100.0
        return f"{val:.0f}%"
    except Exception:
        return str(v)


def _format_cached_age(fetched_at: Optional[str]) -> Optional[str]:
    if not fetched_at:
        return None
    try:
        dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        mins = int((datetime.now(tz.utc) - dt).total_seconds() / 60)
        if mins < 60:
            return f"cached {mins}m ago"
        hours = mins // 60
        rem = mins % 60
        return f"cached {hours}h{rem:02d}m ago"
    except Exception:
        return None


def format_ammo_embed(entry: Dict[str, Any], fetched_at: Optional[str] = None) -> discord.Embed:
    """Build a detailed Discord embed for an ammo entry."""
    item = entry.get("item") or {}
    name = item.get("name") or "Unknown ammo"
    short = item.get("shortName")
    norm = item.get("normalizedName")

    ammo_type = entry.get("ammoType")
    caliber = entry.get("caliber")
    dmg = entry.get("damage")
    pen = entry.get("penetrationPower")
    pen_chance = entry.get("penetrationChance")
    armor_dmg = entry.get("armorDamage")
    pellets = entry.get("projectileCount") or 1
    tracer = entry.get("tracer")
    tracer_color = entry.get("tracerColor")

    color = _pen_color(pen if isinstance(pen, int) else None)

    title = name
    if short and short != name:
        title = f"{name} ({short})"

    embed = discord.Embed(title=title, color=color)
    if norm:
        embed.description = f"`{norm}`"

    # Primary specs
    if caliber:
        embed.add_field(name="Caliber", value=str(caliber), inline=True)
    if ammo_type:
        embed.add_field(name="Ammo Type", value=str(ammo_type), inline=True)

    # Damage details
    if isinstance(dmg, int) and isinstance(pellets, int) and pellets > 1:
        total = dmg * pellets
        embed.add_field(name="Damage", value=f"{pellets} x {dmg} = {total}", inline=True)
    elif dmg is not None:
        embed.add_field(name="Damage", value=str(dmg), inline=True)

    # Penetration details
    if pen is not None:
        embed.add_field(name="Penetration Power", value=str(pen), inline=True)
    if pen_chance is not None:
        embed.add_field(name="Penetration Chance", value=_format_pct(pen_chance), inline=True)

    # Armor and tracer
    if armor_dmg is not None:
        embed.add_field(name="Armor Damage", value=_format_pct(armor_dmg), inline=True)
    if tracer is not None:
        tracer_text = "Yes" if tracer else "No"
        if tracer and tracer_color:
            tracer_text += f" ({tracer_color})"
        embed.add_field(name="Tracer", value=tracer_text, inline=True)

    # Footer with cache age
    age = _format_cached_age(fetched_at)
    if age:
        embed.set_footer(text=age)

    return embed
