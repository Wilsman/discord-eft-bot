from typing import Dict, Any, Optional
import aiohttp
from datetime import datetime, timezone as tz
import os
import json

# Prefer fuzzywuzzy if installed; fallback to stdlib difflib
try:
    from fuzzywuzzy import process as fw_process  # type: ignore
except Exception:  # ModuleNotFoundError or others
    fw_process = None
    import difflib


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
        gridImageLink
        link
        width
        height
        sellFor {
          vendor {
            name
          }
          priceRUB
        }
        buyFor {
          priceRUB
          vendor {
            normalizedName
            ... on TraderOffer {
              minTraderLevel
              buyLimit
            }
          }
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
        gridImageLink
        link
        width
        height
        sellFor {
          vendor {
            name
          }
          priceRUB
        }
        buyFor {
          priceRUB
          vendor {
            normalizedName
            ... on TraderOffer {
              minTraderLevel
              buyLimit
            }
          }
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

        def best_trader_buy(buy_for: Optional[list]) -> Optional[Dict[str, Any]]:
            """Pick the cheapest trader offer from buyFor (exclude flea/other offers)."""
            if not buy_for:
                return None
            candidates = []
            for bf in buy_for:
                vendor = (bf.get("vendor") or {})
                price = bf.get("priceRUB")
                # Only consider trader offers (fragment provides these fields)
                if not isinstance(price, int) or price <= 0:
                    continue
                if "minTraderLevel" not in vendor and "buyLimit" not in vendor:
                    # Likely non-trader (e.g., flea). Skip for PvP trader pricing.
                    continue
                candidates.append({
                    "price": price,
                    "vendor": vendor.get("normalizedName"),
                    "minLevel": vendor.get("minTraderLevel"),
                    "buyLimit": vendor.get("buyLimit"),
                })
            if not candidates:
                return None
            best_b = min(candidates, key=lambda c: c["price"])  # cheapest trader buy price
            return {
                "traderBuyPrice": best_b["price"],
                "traderBuyVendor": best_b["vendor"],
                "traderMinLevel": best_b["minLevel"],
                "traderBuyLimit": best_b["buyLimit"],
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
                # Media and links
                "gridImageLink": it.get("gridImageLink"),
                "link": it.get("link"),
                # Size
                "width": it.get("width"),
                "height": it.get("height"),
            }
            bv = best_vendor(it.get("sellFor"))
            if bv:
                entry.update(bv)
            bt = best_trader_buy(it.get("buyFor"))
            if bt:
                entry.update(bt)
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
                    "gridImageLink": it.get("gridImageLink"),
                    "link": it.get("link"),
                    "width": it.get("width"),
                    "height": it.get("height"),
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
    if fw_process is not None:
        name_match = fw_process.extractOne(search_term.lower(), name_matches.keys())
        shortname_match = fw_process.extractOne(search_term.lower(), shortname_matches.keys())
    else:
        # difflib fallback: emulate (string, score) where score is 0-100
        def best_match_dict(query: str, pool: Dict[str, Any]):
            if not pool:
                return None
            choices = list(pool.keys())
            best = None
            best_score = -1.0
            for choice in choices:
                score = difflib.SequenceMatcher(a=query, b=choice).ratio()
                if score > best_score:
                    best_score = score
                    best = choice
            # Convert 0..1 to 0..100 like fuzzywuzzy
            return (best, int(round(best_score * 100))) if best is not None else None

        name_match = best_match_dict(search_term.lower(), name_matches)
        shortname_match = best_match_dict(search_term.lower(), shortname_matches)

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
