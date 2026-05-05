from typing import Final, Optional, Dict, List, Any
import os
from dotenv import load_dotenv
from discord import Intents, app_commands
import discord
from discord.ext import commands
import aiohttp
import re
import asyncio
from cultist import compute_cultist_selection
import datetime
from cultist_help import get_cultist_help_response as cultist_help_text, build_cultist_help_embed, get_thresholds_table

# ----------------------------------------
# ENV + CONFIG
# ----------------------------------------
load_dotenv()

# ----------------------------------------
# CONSTANTS & SETTINGS
# ----------------------------------------
TOKEN: Final[str] = os.getenv("DISCORD_TOKEN") or ""


def get_circle_timer_label(total: int) -> str:
    if total >= 400_000:
        return "14h / 6h"
    if total >= 350_000:
        return "12h / 14h"
    if total >= 200_000:
        return "12h"
    if total >= 100_000:
        return "8h"
    if total >= 50_000:
        return "5h"
    if total >= 25_000:
        return "4h"
    if total >= 10_000:
        return "3h"
    return "2h"


def fmt_money(value: Any, suffix: str = "₽") -> str:
    return f"{value:,}{suffix}" if isinstance(value, int) and value > 0 else "N/A"


async def build_item_autocomplete_choices(current: str) -> List[app_commands.Choice[str]]:
    from price_search import fetch_items_data, find_item_matches

    if len(current.strip()) < 2:
        return []

    items_data = await fetch_items_data()
    if not items_data:
        return []

    choices: List[app_commands.Choice[str]] = []
    seen_values = set()
    matches = [
        item for item in find_item_matches(items_data, current, limit=12)
        if isinstance(item.get("basePrice"), int) and item.get("basePrice") > 0
    ]
    for item in matches:
        item_name = item.get("name")
        if not item_name or len(item_name) > 100 or item_name in seen_values:
            continue
        seen_values.add(item_name)
        label = (
            f"{item_name} | Base {fmt_money(item.get('basePrice'), '')} | "
            f"PvP {fmt_money(item.get('price'), '')} | PvE {fmt_money(item.get('pvePrice'), '')}"
        )
        if len(label) > 100:
            label = label[:97] + "..."
        choices.append(app_commands.Choice(name=label, value=item_name))
        if len(choices) >= 10:
            break

    return choices

# ----------------------------------------
# DISCORD BOT SETUP
# ----------------------------------------
intents: Intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.tree.command(name="cultist", description="Auto-select items to reach base value threshold with min total cost")
@app_commands.describe(
    threshold="Target total base value in roubles (default: 400000)",
    max_items="Maximum number of items allowed (default: 5)",
    mode="Cost source: PvP (trader) or PvE (flea)",
    randomize="Slightly randomize ties (shuffle candidates before DP)",
)
@app_commands.choices(
    mode=[
        app_commands.Choice(name="PvP (Trader cost)", value="pvp"),
        app_commands.Choice(name="PvE (Flea cost)", value="pve"),
    ]
)
async def cultist(
    interaction: discord.Interaction,
    threshold: int = 400000,
    max_items: int = 5,
    mode: Optional[app_commands.Choice[str]] = None,
    randomize: bool = False,
):
    """Select up to max_items whose base value sum ≥ threshold minimizing total cost.
    Repetition allowed. PvP uses trader buy price (buyFor) with buyLimit, PvE uses flea.
    """
    await interaction.response.defer()
    from price_search import fetch_items_data
    selected_mode = (mode.value if mode else "pvp")
    items_data = await fetch_items_data()
    try:
        result = compute_cultist_selection(
            items_data=items_data,
            threshold=threshold,
            max_items=max_items,
            mode=selected_mode,
            randomize=randomize,
        )
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")
        return

    sel_lines = result.get("sel_lines", [])
    total_value = result.get("total_value", 0)
    total_cost = result.get("total_cost", 0)

    # Build enhanced embed
    mode_label = "PvE (Flea)" if selected_mode == "pve" else "PvP (Trader)"
    met = total_value >= threshold
    color = 0x2ecc71 if met else 0xe67e22  # green if met else orange
    status = "✅ Threshold met" if met else "⚠️ Threshold not met"

    embed = discord.Embed(title="🕯️ Cultist Auto-Select", description=status, color=color)

    # Summary fields
    embed.add_field(name="Mode", value=mode_label, inline=True)
    embed.add_field(name="Threshold", value=f"{threshold:,}₽", inline=True)
    embed.add_field(name="Max items", value=str(max_items), inline=True)
    embed.add_field(name="Total Value", value=f"{total_value:,}₽", inline=True)
    embed.add_field(name="Total Cost", value=f"{total_cost:,}₽", inline=True)

    # Selection list (markdown; allow clickable links)
    if sel_lines:
        chunk: list[str] = []
        current = 0
        for line in sel_lines:
            if current + len(line) + 1 > 1000 and chunk:
                embed.add_field(name="Selection", value="\n".join(chunk), inline=False)
                chunk = []
                current = 0
            chunk.append(line)
            current += len(line) + 1
        if chunk:
            embed.add_field(name="Selection", value="\n".join(chunk), inline=False)

    embed.set_footer(text="Data via Tarkov.dev")

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="circlecheap", description="Find the cheapest current combo for a Cultist Circle target")
@app_commands.describe(
    target="Target Cultist Circle threshold",
    mode="Cost source: PvP trader or PvE flea",
)
@app_commands.choices(
    target=[
        app_commands.Choice(name="350k - 12h/14h chance", value=350000),
        app_commands.Choice(name="400k - 14h/6h pool", value=400000),
    ],
    mode=[
        app_commands.Choice(name="PvP trader", value="pvp"),
        app_commands.Choice(name="PvE flea", value="pve"),
    ],
)
async def circlecheap(
    interaction: discord.Interaction,
    target: app_commands.Choice[int],
    mode: Optional[app_commands.Choice[str]] = None,
):
    from price_search import fetch_items_data

    await interaction.response.defer()

    selected_mode = mode.value if mode else "pvp"
    threshold = target.value
    items_data = await fetch_items_data()
    try:
        result = compute_cultist_selection(
            items_data=items_data,
            threshold=threshold,
            max_items=5,
            mode=selected_mode,
            randomize=False,
        )
        if result.get("total_value", 0) < threshold:
            result = compute_cultist_selection(
                items_data=items_data,
                threshold=threshold + 2_500,
                max_items=5,
                mode=selected_mode,
                randomize=False,
            )
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")
        return

    total_value = result.get("total_value", 0)
    total_cost = result.get("total_cost", 0)
    sel_lines = result.get("sel_lines", [])
    slot_count = 0
    for line in sel_lines:
        match = re.match(r"^x(\d+)", str(line))
        slot_count += int(match.group(1)) if match else 1
    mode_label = "PvE flea" if selected_mode == "pve" else "PvP trader"

    embed = discord.Embed(
        title="Cheapest Cultist Circle Combo",
        description=f"Target: **{threshold:,}₽** ({get_circle_timer_label(threshold)})",
        color=0x2ecc71 if total_value >= threshold else 0xe67e22,
    )
    embed.add_field(name="Mode", value=mode_label, inline=True)
    embed.add_field(name="Total Base", value=f"{total_value:,}₽", inline=True)
    embed.add_field(name="Total Cost", value=f"{total_cost:,}₽", inline=True)
    embed.add_field(name="Slots", value=f"{slot_count}/5", inline=True)

    if sel_lines:
        cleaned_lines = []
        for line in sel_lines:
            cleaned_lines.append(line.replace(" — ", " ").replace(" | ", "\n"))
        embed.add_field(name="Combo", value="\n\n".join(cleaned_lines[:5]), inline=False)

    embed.set_footer(text="Optimized with current Tarkov.dev data. PvP uses trader-buy cost; PvE uses flea cost.")

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="circleown", description="Find cheap filler items for a Cultist Circle combo you already started")
@app_commands.describe(
    item_name="Item you already own",
    quantity="How many of that item you own",
    target="Target Cultist Circle threshold",
    mode="Cost source for filler: PvP trader or PvE flea",
)
@app_commands.choices(
    target=[
        app_commands.Choice(name="350k - 12h/14h chance", value=350000),
        app_commands.Choice(name="400k - 14h/6h pool", value=400000),
    ],
    mode=[
        app_commands.Choice(name="PvP trader", value="pvp"),
        app_commands.Choice(name="PvE flea", value="pve"),
    ],
)
async def circleown(
    interaction: discord.Interaction,
    item_name: str,
    quantity: int,
    target: app_commands.Choice[int],
    mode: Optional[app_commands.Choice[str]] = None,
):
    from price_search import fetch_items_data, find_item_matches

    await interaction.response.defer()

    if quantity <= 0:
        await interaction.followup.send("Quantity must be at least 1.")
        return
    if quantity > 5:
        await interaction.followup.send("Cultist Circle accepts up to 5 items.")
        return

    selected_mode = mode.value if mode else "pvp"
    threshold = target.value
    items_data = await fetch_items_data()
    if not items_data:
        await interaction.followup.send("Error: Could not fetch items data")
        return

    matches = [
        item for item in find_item_matches(items_data, item_name, limit=10)
        if isinstance(item.get("basePrice"), int) and item.get("basePrice") > 0
    ][:5]
    if not matches:
        await interaction.followup.send(f"Could not match '{item_name}'.")
        return

    owned_item = matches[0]
    query_lower = item_name.lower().strip()
    exact_full_match = str(owned_item.get("name") or "").lower() == query_lower
    if len(matches) > 1 and not exact_full_match:
        def fmt_money(value: Any) -> str:
            return f"{value:,}₽" if isinstance(value, int) and value > 0 else "N/A"

        embed = discord.Embed(
            title="Multiple Item Matches",
            description="Use the full item name so I don't pin the wrong item.",
            color=0xf1c40f,
        )
        lines = []
        for index, item in enumerate(matches, start=1):
            name = item.get("name") or "Unknown"
            short_name = item.get("shortName")
            label = f"{name} ({short_name})" if short_name and short_name != name else name
            lines.append(
                f"{index}. {label}\n"
                f"Base {fmt_money(item.get('basePrice'))} | PvP {fmt_money(item.get('price'))} | PvE {fmt_money(item.get('pvePrice'))}"
            )
        embed.add_field(name=f"'{item_name}' could mean:", value="\n".join(lines), inline=False)
        await interaction.followup.send(embed=embed)
        return

    owned_base_each = owned_item.get("basePrice")
    owned_base_total = owned_base_each * quantity
    remaining_slots = 5 - quantity
    remaining_value = max(0, threshold - owned_base_total)
    mode_label = "PvE flea" if selected_mode == "pve" else "PvP trader"

    def item_cost(item: Dict[str, Any]) -> Optional[int]:
        key = "pvePrice" if selected_mode == "pve" else "traderBuyPrice"
        value = item.get(key)
        return value if isinstance(value, int) and value > 0 else None

    owned_cost_each = item_cost(owned_item)
    owned_cost_total = owned_cost_each * quantity if owned_cost_each else None

    filler_result: Optional[Dict[str, Any]] = None
    if remaining_value > 0 and remaining_slots > 0:
        try:
            filler_result = compute_cultist_selection(
                items_data=items_data,
                threshold=remaining_value,
                max_items=remaining_slots,
                mode=selected_mode,
                randomize=False,
            )
            if filler_result.get("total_value", 0) < remaining_value:
                filler_result = compute_cultist_selection(
                    items_data=items_data,
                    threshold=remaining_value + 2_500,
                    max_items=remaining_slots,
                    mode=selected_mode,
                    randomize=False,
                )
        except Exception:
            filler_result = None

    filler_value = filler_result.get("total_value", 0) if filler_result else 0
    filler_cost = filler_result.get("total_cost", 0) if filler_result else 0
    filler_slots = 0
    if filler_result:
        for line in filler_result.get("sel_lines", []):
            match = re.match(r"^x(\d+)", str(line))
            filler_slots += int(match.group(1)) if match else 1
    final_base = owned_base_total + filler_value
    final_cost = filler_cost + owned_cost_total if owned_cost_total is not None else filler_cost

    embed = discord.Embed(
        title="Cultist Circle Owned Item Helper",
        description=f"Target: **{threshold:,}₽** ({get_circle_timer_label(threshold)})",
        color=0x2ecc71 if final_base >= threshold else 0xe67e22,
    )
    owned_name = owned_item.get("name") or item_name
    owned_link = owned_item.get("link")
    owned_label = f"[{owned_name}]({owned_link})" if owned_link else owned_name
    embed.add_field(
        name="Pinned Item",
        value=(
            f"{quantity}x {owned_label}\n"
            f"Base: {owned_base_each:,}₽ each | {owned_base_total:,}₽ total"
        ),
        inline=False,
    )
    embed.add_field(name="Mode", value=mode_label, inline=True)
    embed.add_field(name="Remaining Need", value=f"{remaining_value:,}₽", inline=True)
    embed.add_field(name="Final Base", value=f"{final_base:,}₽", inline=True)
    embed.add_field(name="Estimated Cost", value=f"{final_cost:,}₽", inline=True)
    embed.add_field(name="Slots", value=f"{quantity + filler_slots}/5", inline=True)

    if remaining_value <= 0:
        embed.add_field(name="Filler Needed", value="None. Your pinned item(s) already hit the target.", inline=False)
    elif remaining_slots <= 0:
        embed.add_field(name="Filler Needed", value="No slots left, and the pinned item(s) do not hit the target.", inline=False)
    elif filler_result and filler_result.get("sel_lines"):
        cleaned_lines = []
        for line in filler_result["sel_lines"]:
            cleaned_lines.append(line.replace(" — ", " ").replace(" | ", "\n"))
        embed.add_field(name="Cheapest Filler", value="\n\n".join(cleaned_lines[:5]), inline=False)
    else:
        embed.add_field(name="Cheapest Filler", value="No valid filler combo found for the remaining slots.", inline=False)

    embed.set_footer(text="Pinned item plus optimized filler. PvP uses trader-buy cost; PvE uses flea cost.")

    await interaction.followup.send(embed=embed)


@circleown.autocomplete("item_name")
async def circleown_item_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    return await build_item_autocomplete_choices(current)


@bot.tree.command(name="bosschanges", description="Show today's latest boss spawn changes")
async def bosschanges(interaction: discord.Interaction):
    """Fetch recent boss changes and display today's latest batch, or the newest batch if today is empty."""
    from datetime import datetime, timezone as tz

    await interaction.response.defer()

    url = "https://bossdata.cultistcircle.workers.dev/api/changes?limit=100"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await interaction.followup.send(f"Error fetching boss changes: HTTP {resp.status}")
                    return
                data = await resp.json()
    except Exception as e:
        await interaction.followup.send(f"Error fetching boss changes: {e}")
        return

    if not isinstance(data, list) or not data:
        await interaction.followup.send("No boss changes found.")
        return

    def parse_ts(change: Dict[str, Any]) -> int:
        try:
            return int(change.get("timestamp") or 0)
        except Exception:
            return 0

    sorted_changes = sorted(data, key=parse_ts, reverse=True)
    now = datetime.now(tz.utc)
    today = now.date()

    dated_changes = []
    for change in sorted_changes:
        ts = parse_ts(change)
        if ts <= 0:
            continue
        dt = datetime.fromtimestamp(ts / 1000, tz=tz.utc)
        dated_changes.append((dt, change))

    todays_changes = [(dt, ch) for dt, ch in dated_changes if dt.date() == today]
    if todays_changes:
        selected = todays_changes
        title = "Today's Boss Changes"
        description = "Latest boss spawn updates today."
    else:
        if not dated_changes:
            await interaction.followup.send("No dated boss changes found.")
            return
        latest_date = dated_changes[0][0].date()
        selected = [(dt, ch) for dt, ch in dated_changes if dt.date() == latest_date]
        title = "Latest Boss Changes"
        description = f"No changes today. Latest batch: {dated_changes[0][0].strftime('%d %b %Y')} UTC."

    def fmt_ago(dt: datetime) -> str:
        try:
            delta = now - dt
            total_mins = int(delta.total_seconds() // 60)
            if total_mins < 1:
                return "just now"
            days = total_mins // (60 * 24)
            hours = (total_mins // 60) % 24
            mins = total_mins % 60
            if days > 0:
                return f"{days}d{hours}h"
            if hours > 0:
                return f"{hours}h{mins}m"
            return f"{mins}m"
        except Exception:
            return "N/A"

    def pretty_token(value: Any) -> str:
        raw = str(value or "Unknown")
        labels = {
            "regular": "PvP",
            "pve": "PvE",
            "arenafighter": "Arena Fighter",
            "bossAdded": "added",
            "bossRemoved": "removed",
            "spawnChance": "spawn",
        }
        if raw in labels:
            return labels[raw]
        return raw.replace("_", " ").title()

    def format_change(change: Dict[str, Any]) -> str:
        field = change.get("field")
        boss = pretty_token(change.get("boss"))
        old_val = change.get("old_value") or "?"
        new_val = change.get("new_value") or "?"
        if field == "bossAdded":
            return f"{boss} added ({new_val})"
        if field == "bossRemoved":
            return f"{boss} removed"
        if field == "spawnChance":
            return f"{boss} {old_val} -> {new_val}"
        return f"{boss} {pretty_token(field)}: {old_val} -> {new_val}"

    grouped: Dict[str, List[str]] = {}
    latest_dt = selected[0][0]
    for dt, change in selected[:12]:
        key = f"{pretty_token(change.get('map'))} ({pretty_token(change.get('game_mode'))})"
        grouped.setdefault(key, []).append(format_change(change))
        if dt > latest_dt:
            latest_dt = dt

    embed = discord.Embed(
        title=title,
        description=description,
        color=0x9b59b6,
    )

    for key, lines in list(grouped.items())[:6]:
        embed.add_field(name=key, value="\n".join(lines[:4]), inline=False)

    shown = sum(len(lines[:4]) for lines in list(grouped.values())[:6])
    total = len(selected)
    suffix = f"Showing {shown}/{total} changes" if total > shown else f"{total} change(s)"
    embed.set_footer(text=f"Source: Cultist Circle • {fmt_ago(latest_dt)} ago • {suffix}")

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="price", description="Search for item prices")
@app_commands.describe(
    item_name="Name of the item to search for",
    mode="Choose PvP or PvE price data (default: PvP)",
)
@app_commands.choices(
    mode=[
        app_commands.Choice(name="PvP", value="pvp"),
        app_commands.Choice(name="PvE", value="pve"),
    ]
)
async def price(interaction: discord.Interaction, item_name: str, mode: Optional[app_commands.Choice[str]] = None):
    from price_search import fetch_items_data, find_item
    from datetime import datetime, timezone as tz
    
    await interaction.response.defer()
    items_data = await fetch_items_data()
    
    if not items_data:
        await interaction.followup.send("Error: Could not fetch items data")
        return
        
    item = find_item(items_data, item_name)
    if not item:
        await interaction.followup.send(f"Could not find item matching '{item_name}'")
        return

    # Parse timestamps based on selected mode
    current_dt = datetime.now(tz.utc)
    selected_mode = (mode.value if mode else "pvp")
    updated_iso = item.get("pveUpdated") if selected_mode == "pve" else item.get("updated")
    last_mins: Optional[int] = None
    if updated_iso:
        dt_parsed = datetime.fromisoformat(updated_iso.replace("Z", "+00:00"))
        last_mins = int((current_dt - dt_parsed).total_seconds() / 60)
    
    # Format time strings
    def format_time(mins: Optional[int]) -> str:
        if mins is None:
            return "N/A"
        hours = mins // 60
        minutes = mins % 60
        return f"{hours}h{minutes}m" if hours > 0 else f"{minutes}m"

    # Create embed header (title + link + thumbnail)
    link = item.get("link")
    if link:
        embed = discord.Embed(
            title=item["name"],
            color=0x2b2d31,
            url=link,
        )
    else:
        embed = discord.Embed(
            title=item["name"],
            color=0x2b2d31,
        )
    thumb = item.get("gridImageLink")
    if thumb:
        embed.set_thumbnail(url=thumb)

    # Primary price block (two-column inline fields)
    # Only show Flea when the selected mode actually has a flea price.
    flea_price_raw = item.get('pvePrice') if selected_mode == 'pve' else item.get('price')
    if flea_price_raw is not None:
        embed.add_field(name="Flea Market Price", value=f"**{flea_price_raw:,}₽**", inline=True)

    trader_price = item.get('traderSellPrice')
    if trader_price is not None:
        embed.add_field(name="Trader Buying Price", value=f"**{trader_price:,}₽**", inline=True)

    # Price per slot (based on selected mode flea price)
    w_raw = item.get('width')
    h_raw = item.get('height')
    def to_int(v: Any) -> Optional[int]:
        try:
            return int(v) if v is not None else None
        except Exception:
            return None
    w = to_int(w_raw)
    h = to_int(h_raw)
    slots = (w * h) if (isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0) else None
    # Use selected mode flea for PPS; in PvP, if missing, fallback to trader price just for PPS.
    pps_price = flea_price_raw
    if pps_price is None and selected_mode == 'pvp':
        tf = item.get('traderSellPrice')
        if isinstance(tf, int):
            pps_price = tf
    if pps_price is not None and slots and slots > 0:
        pps = int(round(pps_price / slots))
        embed.add_field(name="Price Per Slot", value=f"{pps:,}₽", inline=True)

    # Highlighted Base Price (yellow accent via emoji)
    base_price = item.get('basePrice')
    if base_price is not None:
        embed.add_field(name="🟡 Base Price", value=f"**{base_price:,}₽**", inline=True)

    # Secondary block
    avg_24h = item.get('avg24hPrice')
    if isinstance(avg_24h, int):
        embed.add_field(name="24 Hour Price AVG", value=f"{avg_24h:,}₽", inline=True)

    trader_name = item.get('traderSellName') or "Unknown Trader"
    embed.add_field(name="Trader to sell to", value=trader_name, inline=True)

    # Footer: last updated and attribution (fallback to other mode if missing)
    if last_mins is None:
        fallback_iso = item.get('updated') if selected_mode == 'pve' else item.get('pveUpdated')
        if fallback_iso:
            fb_dt = datetime.fromisoformat(fallback_iso.replace("Z", "+00:00"))
            last_mins = int((current_dt - fb_dt).total_seconds() / 60)
    updated_str = f"Last Updated: {format_time(last_mins)} ago" if last_mins is not None else "Last Updated: N/A"
    embed.set_footer(text=f"{updated_str} - Data provided by Tarkov.dev")

    await interaction.followup.send(embed=embed)


@price.autocomplete("item_name")
async def price_item_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    return await build_item_autocomplete_choices(current)

@bot.tree.command(name="circlevalue", description="Show one item's Cultist Circle value efficiency")
@app_commands.describe(
    item_name="Name of the item to check",
)
async def circlevalue(interaction: discord.Interaction, item_name: str):
    from math import ceil
    from price_search import fetch_items_data, find_item

    await interaction.response.defer()

    items_data = await fetch_items_data()
    if not items_data:
        await interaction.followup.send("Error: Could not fetch items data")
        return

    item = find_item(items_data, item_name)
    if not item:
        await interaction.followup.send(f"Could not find item matching '{item_name}'")
        return

    base_value = item.get("basePrice")
    if not isinstance(base_value, int) or base_value <= 0:
        await interaction.followup.send(f"Could not find a valid base value for '{item_name}'")
        return

    link = item.get("link")
    embed = discord.Embed(
        title=item.get("name") or item_name,
        color=0x8e44ad,
        url=link if link else None,
    )

    thumb = item.get("gridImageLink")
    if thumb:
        embed.set_thumbnail(url=thumb)

    def fmt_money(value: Any) -> str:
        return f"{value:,}₽" if isinstance(value, int) and value > 0 else "N/A"

    def fmt_efficiency(cost: Any) -> str:
        if not isinstance(cost, int) or cost <= 0:
            return "N/A"
        return f"{base_value / cost:.2f} base/₽"

    pvp_cost = item.get("price")
    pve_cost = item.get("pvePrice")

    embed.add_field(name="Base Value", value=f"**{base_value:,}₽**", inline=True)
    embed.add_field(name="PvP Flea Cost", value=fmt_money(pvp_cost), inline=True)
    embed.add_field(name="PvE Flea Cost", value=fmt_money(pve_cost), inline=True)
    embed.add_field(name="PvP Efficiency", value=fmt_efficiency(pvp_cost), inline=True)
    embed.add_field(name="PvE Efficiency", value=fmt_efficiency(pve_cost), inline=True)

    copies_350 = ceil(350_000 / base_value)
    copies_400 = ceil(400_000 / base_value)
    target_lines = [
        f"350k: {'yes' if copies_350 <= 5 else 'no'} ({copies_350}x needed)",
        f"400k: {'yes' if copies_400 <= 5 else 'no'} ({copies_400}x needed)",
    ]
    embed.add_field(name="Can Reach Alone", value="\n".join(target_lines), inline=False)

    copy_lines = []
    for count in range(1, 6):
        total = base_value * count
        copy_lines.append(f"{count}x: {total:,}₽ - {get_circle_timer_label(total)}")
    embed.add_field(name="1-5 Copies", value="\n".join(copy_lines), inline=False)

    embed.set_footer(text="Base value math via Tarkov.dev. Weapons/durability may have special Circle behavior.")

    await interaction.followup.send(embed=embed)


@circlevalue.autocomplete("item_name")
async def circlevalue_item_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    return await build_item_autocomplete_choices(current)


@bot.tree.command(name="circlecheck", description="Check a Cultist Circle combo's total base value")
@app_commands.describe(
    combo="Example: 3x Ratchet Wrench & 1x Flash Drive",
)
async def circlecheck(interaction: discord.Interaction, combo: str):
    from price_search import fetch_items_data, find_item_matches

    await interaction.response.defer()

    def parse_combo(raw_combo: str) -> List[Dict[str, Any]]:
        parts = [p.strip() for p in re.split(r"\s*(?:&|\+|,|\band\b)\s*", raw_combo, flags=re.IGNORECASE) if p.strip()]
        parsed: List[Dict[str, Any]] = []
        for part in parts:
            match = re.match(r"^(?:(\d+)\s*x?\s+|x\s*(\d+)\s+)?(.+?)$", part, flags=re.IGNORECASE)
            if not match:
                continue
            quantity_raw = match.group(1) or match.group(2)
            quantity = int(quantity_raw) if quantity_raw else 1
            name = match.group(3).strip()
            if quantity <= 0 or not name:
                continue
            parsed.append({"quantity": quantity, "name": name})
        return parsed

    parsed_items = parse_combo(combo)
    if not parsed_items:
        await interaction.followup.send("Could not parse that combo. Try `3x Ratchet Wrench & 1x Flash Drive`.")
        return

    total_quantity = sum(entry["quantity"] for entry in parsed_items)
    if total_quantity > 5:
        await interaction.followup.send("Cultist Circle accepts up to 5 items. That combo has too many items.")
        return

    items_data = await fetch_items_data()
    if not items_data:
        await interaction.followup.send("Error: Could not fetch items data")
        return

    rows: List[Dict[str, Any]] = []
    missing: List[str] = []
    ambiguous: List[Dict[str, Any]] = []
    total_base = 0
    total_pvp_cost = 0
    total_pve_cost = 0
    has_pvp_cost = True
    has_pve_cost = True

    for entry in parsed_items:
        matches = [
            item for item in find_item_matches(items_data, entry["name"], limit=10)
            if isinstance(item.get("basePrice"), int) and item.get("basePrice") > 0
        ][:5]
        if not matches:
            missing.append(entry["name"])
            continue
        item = matches[0]
        query_lower = entry["name"].lower().strip()
        top_name = str(item.get("name") or "").lower()
        exact_full_match = top_name == query_lower
        if len(matches) > 1 and not exact_full_match:
            ambiguous.append({"query": entry["name"], "matches": matches[:5]})
            continue

        quantity = entry["quantity"]
        base_value = item.get("basePrice")
        if not isinstance(base_value, int) or base_value <= 0:
            missing.append(entry["name"])
            continue

        line_base = base_value * quantity
        total_base += line_base

        pvp_cost = item.get("price")
        if isinstance(pvp_cost, int) and pvp_cost > 0:
            total_pvp_cost += pvp_cost * quantity
        else:
            has_pvp_cost = False

        pve_cost = item.get("pvePrice")
        if isinstance(pve_cost, int) and pve_cost > 0:
            total_pve_cost += pve_cost * quantity
        else:
            has_pve_cost = False

        rows.append({
            "quantity": quantity,
            "name": item.get("name") or entry["name"],
            "base_value": base_value,
            "line_base": line_base,
            "link": item.get("link"),
            "image": item.get("gridImageLink"),
        })

    if missing:
        await interaction.followup.send(f"Could not match: {', '.join(missing)}")
        return

    if ambiguous:
        def fmt_money(value: Any) -> str:
            return f"{value:,}₽" if isinstance(value, int) and value > 0 else "N/A"

        embed = discord.Embed(
            title="Multiple Item Matches",
            description="Use the full item name in your combo so I don't pick the wrong one.",
            color=0xf1c40f,
        )
        for entry in ambiguous[:3]:
            lines = []
            for index, item in enumerate(entry["matches"], start=1):
                name = item.get("name") or "Unknown"
                short_name = item.get("shortName")
                label = f"{name} ({short_name})" if short_name and short_name != name else name
                lines.append(
                    f"{index}. {label}\n"
                    f"Base {fmt_money(item.get('basePrice'))} | PvP {fmt_money(item.get('price'))} | PvE {fmt_money(item.get('pvePrice'))}"
                )
            embed.add_field(name=f"'{entry['query']}' could mean:", value="\n".join(lines), inline=False)
        embed.set_footer(text="Example: 3x Ratchet Wrench & 1x Secure Flash drive")
        await interaction.followup.send(embed=embed)
        return

    if not rows:
        await interaction.followup.send("Could not find valid base values for that combo.")
        return

    color = 0x2ecc71 if total_base >= 400_000 else 0xf1c40f if total_base >= 350_000 else 0xe67e22
    embed = discord.Embed(
        title="Cultist Circle Combo Check",
        description=f"**Total Base Value:** {total_base:,}₽\n**Timer Pool:** {get_circle_timer_label(total_base)}",
        color=color,
    )

    first_image = next((row["image"] for row in rows if row.get("image")), None)
    if first_image:
        embed.set_thumbnail(url=first_image)

    for row in rows:
        name = f"[{row['name']}]({row['link']})" if row.get("link") else row["name"]
        image_link = f"\n[Icon]({row['image']})" if row.get("image") else ""
        embed.add_field(
            name=f"{row['quantity']}x {name}",
            value=f"Base: {row['base_value']:,}₽ each\nLine: {row['line_base']:,}₽{image_link}",
            inline=False,
        )

    threshold_lines = [
        f"350k: {'yes' if total_base >= 350_000 else 'no'}",
        f"400k: {'yes' if total_base >= 400_000 else 'no'}",
        f"Slots used: {total_quantity}/5",
    ]
    embed.add_field(name="Thresholds", value="\n".join(threshold_lines), inline=True)

    cost_lines = [
        f"PvP flea: {total_pvp_cost:,}₽" if has_pvp_cost else "PvP flea: N/A",
        f"PvE flea: {total_pve_cost:,}₽" if has_pve_cost else "PvE flea: N/A",
    ]
    embed.add_field(name="Total Cost", value="\n".join(cost_lines), inline=True)
    embed.set_footer(text="Base value math via Tarkov.dev. Weapons/durability may have special Circle behavior.")

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="circlehot", description="List current high-efficiency Cultist Circle sacrifice items")
@app_commands.describe(
    mode="Price source: PvP flea or PvE flea",
    max_cost="Ignore items above this flea price (default: 250000)",
)
@app_commands.choices(
    mode=[
        app_commands.Choice(name="PvP flea", value="pvp"),
        app_commands.Choice(name="PvE flea", value="pve"),
    ]
)
async def circlehot(
    interaction: discord.Interaction,
    mode: Optional[app_commands.Choice[str]] = None,
    max_cost: int = 250_000,
):
    from price_search import fetch_items_data

    await interaction.response.defer()

    selected_mode = mode.value if mode else "pvp"
    price_key = "pvePrice" if selected_mode == "pve" else "price"
    mode_label = "PvE flea" if selected_mode == "pve" else "PvP flea"
    sane_max_cost = max(1_000, min(max_cost, 5_000_000))

    items_data = await fetch_items_data()
    if not items_data or "items" not in items_data:
        await interaction.followup.send("Error: Could not fetch items data")
        return

    candidates: List[Dict[str, Any]] = []
    for item in items_data["items"]:
        base_value = item.get("basePrice")
        price = item.get(price_key)
        if not isinstance(base_value, int) or base_value < 10_000:
            continue
        if not isinstance(price, int) or price < 1_000 or price > sane_max_cost:
            continue

        ratio = base_value / price
        if ratio <= 0:
            continue

        candidates.append({
            "name": item.get("name") or item.get("shortName") or "Unknown",
            "base_value": base_value,
            "price": price,
            "ratio": ratio,
            "link": item.get("link"),
            "image": item.get("gridImageLink"),
        })

    if not candidates:
        await interaction.followup.send(f"No good {mode_label} candidates found under {sane_max_cost:,}₽.")
        return

    candidates.sort(key=lambda entry: (entry["ratio"], entry["base_value"]), reverse=True)
    top_items = candidates[:5]

    embed = discord.Embed(
        title="Hot Cultist Circle Sacrifices",
        description=f"Top 5 by base value per rouble using **{mode_label}** prices.\nMax item cost: {sane_max_cost:,}₽",
        color=0xe67e22,
    )

    first_image = next((item["image"] for item in top_items if item.get("image")), None)
    if first_image:
        embed.set_thumbnail(url=first_image)

    for index, item in enumerate(top_items, start=1):
        name = f"[{item['name']}]({item['link']})" if item.get("link") else item["name"]
        one_item_timer = get_circle_timer_label(item["base_value"])
        copies_350 = (350_000 + item["base_value"] - 1) // item["base_value"]
        copies_400 = (400_000 + item["base_value"] - 1) // item["base_value"]
        target_line = (
            f"350k: {copies_350}x" if copies_350 <= 5 else "350k: no"
        ) + " | " + (
            f"400k: {copies_400}x" if copies_400 <= 5 else "400k: no"
        )

        embed.add_field(
            name=f"{index}. {name}",
            value=(
                f"Base: {item['base_value']:,}₽ | Cost: {item['price']:,}₽\n"
                f"Efficiency: {item['ratio']:.2f} base/₽ | 1x: {one_item_timer}\n"
                f"{target_line}"
            ),
            inline=False,
        )

    embed.set_footer(text="Filtered to positive flea prices and base value >= 10k. Data via Tarkov.dev.")

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="ammo", description="Look up information about ammunition types")
async def ammo(interaction: discord.Interaction, name: str):
    """Look up information about ammunition types using GraphQL data"""
    await interaction.response.defer()

    # Import here to keep related code localized to the ammo section
    from ammo_search import fetch_ammo_data, find_ammo, format_ammo_embed as build_ammo_embed

    data = await fetch_ammo_data()
    if not data or not data.get("ammo"):
        await interaction.followup.send(
            embed=discord.Embed(
                title="Ammo Data Unavailable",
                description="Couldn't fetch ammo data. Please try again later.",
                color=0xFF0000,
            )
        )
        return

    entry = find_ammo(data, name)
    if not entry:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Ammo Not Found",
                description=f"No ammunition found matching '{name}'",
                color=0xFF0000,
            )
        )
        return

    embed = build_ammo_embed(entry, data.get("fetchedAt"))
    await interaction.followup.send(embed=embed)

# ----------------------------------------
# HIDEOUT COMMANDS
# ----------------------------------------
def get_cultist_help_response(question: str) -> str:
    # Delegates to implementation in cultist_help.py (logic moved out of main)
    return cultist_help_text(question)

@bot.tree.command(name="circlehelp", description="Get information about Cultist Circle timings and thresholds")
async def circlehelp(interaction: discord.Interaction, question: str):
    """
    Get information about Cultist Circle timings and thresholds
    
    Example questions:
    - "6h chance"
    - "14h loot"
    - "base value calculation"
    - "moonshine example"
    - "weapon values"
    - "thresholds"
    - "hardcore tips"
    """
    embed = build_cultist_help_embed(question)
    
    await interaction.response.send_message(embed=embed, ephemeral=False)

@bot.tree.command(name="circlethresholds", description="Display Cultist Circle value thresholds and timing table")
async def circlethresholds(interaction: discord.Interaction):
    """Display a comprehensive table of Cultist Circle value thresholds and their corresponding timings."""
    table = get_thresholds_table()
    
    await interaction.response.send_message(table, ephemeral=False)

# ----------------------------------------
# DISCORD BOT EVENTS
# ----------------------------------------
@bot.event
async def on_ready() -> None:
    print(f"{bot.user} has connected to Discord!")

    async def warm_items_cache() -> None:
        try:
            from price_search import fetch_items_data

            data = await fetch_items_data()
            count = len(data.get("items", [])) if data else 0
            print(f"Warmed item cache with {count} item(s)")
        except Exception as e:
            print(f"Failed to warm item cache: {e}")

    asyncio.create_task(warm_items_cache())
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.event
async def on_message(message: discord.Message) -> None:
    # Process messages if needed
    await bot.process_commands(message)

# ----------------------------------------
# ENTRY POINT
# ----------------------------------------
def main() -> None:
    load_dotenv()
    TOKEN: Final[str] = os.getenv("DISCORD_TOKEN", "")
    if not TOKEN:
        raise ValueError("Bot token not found")
        
    bot.run(TOKEN)

if __name__ == "__main__":
    main()
