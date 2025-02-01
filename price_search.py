from typing import Dict, Any, Optional
import aiohttp
from datetime import datetime, timezone as tz
from fuzzywuzzy import process


async def fetch_items_data() -> Optional[Dict[str, Any]]:
    """Fetch items data from the API"""
    url = "https://my-first-worker.cultistcircle.workers.dev/?items=true"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
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
    pvp_price = "{:,}".format(item["price"])
    trader_price = "{:,}".format(item["traderSellPrice"]) if "traderSellPrice" in item else "N/A"
    trader_info = f" | Trader: {trader_price}₽ {item.get('traderSellName', 'N/A')}"

    return f"💰 {item['name']} | PvP: {pvp_price}₽ ({format_time(pvp_mins)} ago) | PvE: {pve_price}₽ ({format_time(pve_mins)} ago){trader_info}"
