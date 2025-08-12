from typing import Dict, Any, Optional
import aiohttp
from datetime import datetime, timezone as tz
from fuzzywuzzy import process
import os
import json


# Cache configuration
CACHE_FILE = os.path.join(os.path.dirname(__file__), "items_cache.json")
CACHE_TTL_SECONDS = 600  # 10 minutes


async def fetch_items_data() -> Optional[Dict[str, Any]]:
    """
    Fetch items from the GraphQL API and write to a cache file.

    Returns a dict with shape: { "items": [...], "fetchedAt": iso_string }
    """
    # 1) Serve fresh cache when available
    try:
        if os.path.exists(CACHE_FILE):
            mtime = os.path.getmtime(CACHE_FILE)
            if (datetime.now(tz.utc).timestamp() - mtime) < CACHE_TTL_SECONDS:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
    except Exception as e:
        print(f"Cache read error: {e}")

    # 2) Fetch from GraphQL and rebuild cache
    url = "https://api.tarkov.dev/graphql"
    query = """
    {
      pvpItems: items(gameMode: regular) {
        id
        name
        shortName
        lastLowPrice
        avg24hPrice
        basePrice
        sellFor {
          vendor {
            name
          }
          priceRUB
        }
        updated
      }
      pveItems: items(gameMode: pve) {
        id
        name
        shortName
        lastLowPrice
        avg24hPrice
        basePrice
        sellFor {
          vendor {
            name
          }
          priceRUB
        }
        updated
      }
    }
    """

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"query": query}) as response:
                if response.status != 200:
                    print(f"GraphQL error: HTTP {response.status}")
                    return None
                payload = await response.json()

        data = payload.get("data", {})
        pvp_items = data.get("pvpItems", [])
        pve_items = data.get("pveItems", [])

        # Build lookup by id for PvP, then enrich with PvE
        by_id: Dict[str, Dict[str, Any]] = {}

        def best_vendor(sell_for: Optional[list]) -> Optional[Dict[str, Any]]:
            if not sell_for:
                return None
            best = max(sell_for, key=lambda s: (s.get("priceRUB") or 0))
            return {
                "traderSellPrice": best.get("priceRUB"),
                "traderSellName": (best.get("vendor") or {}).get("name")
            }

        for it in pvp_items:
            entry: Dict[str, Any] = {
                "id": it.get("id"),
                "name": it.get("name"),
                "shortName": it.get("shortName"),
                # PvP flea
                "price": it.get("lastLowPrice"),
                "avg24hPrice": it.get("avg24hPrice"),
                # Base and updated
                "basePrice": it.get("basePrice"),
                "updated": it.get("updated"),
            }
            bv = best_vendor(it.get("sellFor"))
            if bv:
                entry.update(bv)
            by_id[it.get("id")] = entry

        for it in pve_items:
            eid = it.get("id")
            tgt = by_id.get(eid)
            if tgt is None:
                tgt = {
                    "id": it.get("id"),
                    "name": it.get("name"),
                    "shortName": it.get("shortName"),
                    "basePrice": it.get("basePrice"),
                }
                by_id[eid] = tgt
            tgt["pvePrice"] = it.get("lastLowPrice")
            tgt["pveUpdated"] = it.get("updated")

        items_list = list(by_id.values())
        result = {
            "items": items_list,
            "fetchedAt": datetime.now(tz.utc).isoformat()
        }

        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False)
        except Exception as e:
            print(f"Cache write error: {e}")

        return result
    except Exception as e:
        print(f"Error fetching items data: {e}")
        return None


def find_item(items_data: Dict[str, Any], search_term: str) -> Optional[Dict[str, Any]]:
    """Find item using fuzzy matching on both name and shortName"""
    if not items_data or "items" not in items_data:
        return None

    # Create dictionaries for both name and shortName matches
    name_matches = {}
    shortname_matches = {}

    for item in items_data["items"]:
        name_matches[item["name"].lower()] = item
        # Some items might not have shortName, so we check first
        if "shortName" in item and item["shortName"]:
            shortname_matches[item["shortName"].lower()] = item

    # Try matching against both name and shortName
    name_match = process.extractOne(search_term.lower(), name_matches.keys())
    shortname_match = process.extractOne(search_term.lower(), shortname_matches.keys())

    # Compare the match scores and take the better one
    best_match = None
    best_score = 0

    if name_match and name_match[1] >= 80:
        best_match = name_matches[name_match[0]]
        best_score = name_match[1]

    if shortname_match and shortname_match[1] >= 80:
        if shortname_match[1] > best_score:
            best_match = shortname_matches[shortname_match[0]]

    return best_match


def format_price_response(item: Dict[str, Any]) -> str:
    """Format the price response string with both PvP and PvE prices"""
    # Parse timestamps and keep them timezone-aware
    pvp_dt = datetime.fromisoformat(item["updated"].replace("Z", "+00:00"))
    current_dt = datetime.now(tz.utc)

    # Check if both PvE fields exist in the item
    if "pveUpdated" in item and "pvePrice" in item:
        pve_dt = datetime.fromisoformat(item["pveUpdated"].replace("Z", "+00:00"))
        pve_mins = int((current_dt - pve_dt).total_seconds() / 60)
        pve_price = "{:,}".format(item["pvePrice"])
    else:
        pve_mins = None
        pve_price = "N/A"

    pvp_mins = int((current_dt - pvp_dt).total_seconds() / 60)

    # Format time strings
    def format_time(mins: Optional[int]) -> str:
        if mins is None:
            return "N/A"
        hours = mins // 60
        minutes = mins % 60
        return f"{hours}h{minutes}m" if hours > 0 else f"{minutes}m"

    # Format prices with commas
    pvp_val = item.get("price")
    pvp_price = "{:,}".format(pvp_val) if isinstance(pvp_val, int) else "N/A"
    trader_val = item.get("traderSellPrice")
    trader_price = "{:,}".format(trader_val) if isinstance(trader_val, int) else "N/A"
    trader_info = f" | Trader: {trader_price}₽ {item.get('traderSellName', 'N/A')}"

    return f"💰 {item['name']} | PvP: {pvp_price}₽ ({format_time(pvp_mins)} ago) | PvE: {pve_price}₽ ({format_time(pve_mins)} ago){trader_info}"
