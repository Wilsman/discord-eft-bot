from typing import Final, Optional, Dict, List, Any, Union
import os
from dotenv import load_dotenv
from discord import Intents, app_commands
import discord
from discord.ext import commands
import aiohttp
import json
import requests
import ollama
from cultist import compute_cultist_selection
import datetime
from cultist_help import get_cultist_help_response as cultist_help_text, build_cultist_help_embed, get_thresholds_table
import traceback
from dataclasses import dataclass
from typing import Optional

# ----------------------------------------
# COMMUNITY / PERPLEXICA DATA (example)
# ----------------------------------------
# If you have additional context or data for your "community" usage,
# you can define it in a separate file and import it here.
# For demonstration, we include placeholders:
COMMUNITY_LINKS = {}
COMMUNITY_CONTEXT = ""

# ----------------------------------------
# ENV + CONFIG
# ----------------------------------------
load_dotenv()

# ----------------------------------------
# CONSTANTS & SETTINGS
# ----------------------------------------
TOKEN: Final[str] = os.getenv("DISCORD_TOKEN") or ""
ENABLE_QUESTION_CLEANING = False
OLLAMA_MODEL = "llama3.1:latest"  # Adjust to your local Ollama model

# ----------------------------------------
# ADDITIONAL DATACLASSES / STRUCTS
# ----------------------------------------
@dataclass
class ChatResponse:
    content: str
    error: Optional[str] = None

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

@bot.tree.command(name="bosschanges", description="Show the latest 3 boss spawn changes")
async def bosschanges(interaction: discord.Interaction):
    """Fetch latest boss changes and display the newest 3 in an embed."""
    from datetime import datetime, timezone as tz

    await interaction.response.defer()

    url = "https://bossdata.cultistcircle.workers.dev/changes"
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

    # Sort by timestamp desc and take latest 3
    changes = sorted(data, key=lambda x: x.get("timestamp", 0), reverse=True)[:3]

    def fmt_ago(ts_ms: int) -> str:
        try:
            dt = datetime.fromtimestamp(max(0, ts_ms) / 1000, tz=tz.utc)
            now = datetime.now(tz.utc)
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

    embed = discord.Embed(
        title="Latest Boss Changes",
        description="Recent updates to boss spawn settings",
        color=0x9b59b6,
    )

    for ch in changes:
        boss = (ch.get("boss") or "Unknown").title()
        game_mode = ch.get("game_mode") or "regular"
        map_name = (ch.get("map") or "Unknown").title()
        field = ch.get("field") or "field"
        old_val = ch.get("old_value") or "?"
        new_val = ch.get("new_value") or "?"
        ts = ch.get("timestamp") or 0

        name = f"{boss} — {map_name} ({game_mode})"
        value = f"{field}: {old_val} → {new_val}\n{fmt_ago(int(ts))} ago"
        embed.add_field(name=name, value=value, inline=False)

    embed.set_footer(text="Source: Cultist Circle")

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

@bot.tree.command(name="base", description="Show item's base value")
@app_commands.describe(
    item_name="Name of the item to search for",
)
async def base(interaction: discord.Interaction, item_name: str):
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

    base_price = item.get("basePrice")
    base_val = f"**{base_price:,}₽**" if isinstance(base_price, int) else "N/A"
    embed.add_field(name="Base Value", value=base_val, inline=False)

    await interaction.followup.send(embed=embed)

# @bot.tree.command(name="ai", description="Ask AI a Question")
# @app_commands.describe(
#     question="Your question to the ai"
# )
# async def ai_search(
#     interaction: discord.Interaction, 
#     question: str
# ):
#     await interaction.response.defer()
    
#     try:
#         # Add time context to the question
#         time_context = format_time_context()
#         context_message = create_chat_prompt(question, time_context)
        
#         # Search using Perplexica
#         response = await search_perplexica(context_message)
        
#         # Handle the response
#         if isinstance(response, ChatResponse):
#             if response.error:
#                 await interaction.followup.send(f"Error: {response.error}")
#             else:
#                 # Truncate response if it's too long
#                 content = response.content
#                 if len(content) > 1900:  # Leave room for ellipsis and source
#                     # Find the last complete sentence before the limit
#                     last_period = content[:1900].rfind('.')
#                     if last_period == -1:
#                         last_period = 1900
#                     content = content[:last_period + 1] + "\n\n[Response truncated due to length...]"
#                 await interaction.followup.send(content)
#         else:
#             # For backward compatibility with string responses
#             content = str(response)
#             if len(content) > 1900:
#                 content = content[:1900] + "\n\n[Response truncated due to length...]"
#             await interaction.followup.send(content)
            
#     except Exception as e:
#         error_message = f"An error occurred while processing your question: {str(e)}"
#         await interaction.followup.send(error_message)

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
# AMMO FUNCTIONS (migrated to ammo_search.py)
# ----------------------------------------

# ----------------------------------------
# EXISTING BOT FUNCTIONS
# ----------------------------------------
async def get_ai_response(prompt: str) -> Union[ChatResponse, str]:
    try:
        return await search_perplexica(prompt)
    except Exception as e:
        return ChatResponse(content="", error=str(e))

# ----------------------------------------
# NEW PERPLEXICA / OLLAMA FUNCTIONS
# ----------------------------------------
def format_time_context() -> str:
    current_datetime = datetime.datetime.now()
    date_str = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"TIME CONTEXT:\n"
        f"- Current: {date_str}\n"
        f"- For events: Use exact hours/minutes for today, days for future"
    )


def create_chat_prompt(original_question: str, context_message: str) -> str:
    """Create a chat prompt for Ollama"""
    return f"""Based on this context, answer the question concisely and accurately.
Question: {original_question}
Context: {context_message}
Response: """


def format_qa_response(answer: str, source_url: Optional[str] = None) -> str:
    """Format Q&A response with better formatting and source attribution"""
    response_parts = []
    
    # Add the main answer with proper formatting
    response_parts.append(f"**Answer:** {answer}")
    
    # Add source if available
    if source_url:
        response_parts.append(f"\n**Source:** {source_url}")
    
    return "\n".join(response_parts)


async def get_concise_response(
    long_answer: str,
    original_question: str,
    sources: List[Dict[str, Any]]
) -> ChatResponse:
    try:
        # Get response from Ollama
        response = await ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": long_answer}]
        )
        
        answer = response.messages[-1].content.strip()
        
        # Get source URL if available
        source_url = None
        if sources and len(sources) > 0:
            # Check for Khorovod-specific case
            if "latest tarkov event task" in original_question.lower():
                for source in sources:
                    if "khorovod" in source.get("title", "").lower():
                        source_url = source.get("url")
                        break
            # Default to first source if no Khorovod source found
            if not source_url and sources[0].get("url"):
                source_url = sources[0]["url"]
        
        # Format the response
        formatted_response = format_qa_response(answer, source_url)
        return ChatResponse(content=formatted_response)

    except Exception as e:
        error_msg = f"Error generating response: {str(e)}"
        return ChatResponse(content="I encountered an error while processing your question.", error=error_msg)


def clean_question_with_ollama(question: str) -> str:
    if not ENABLE_QUESTION_CLEANING:
        print("Question cleaning disabled, using original:", question)
        return question

    try:
        prompt = (
            f"Your task is to ONLY fix grammar and formatting. "
            f"DO NOT add or change any facts. "
            f"Clean this question: '{question}'\n"
            f"Return ONLY the cleaned question."
        )
        response = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
        cleaned = response["message"]["content"].strip().strip("\"'")
        print("Question cleaned:", cleaned)
        return cleaned
    except Exception as err:
        print(f"Question cleaning failed: {err}")
        return question


async def search_perplexica(
    query: str, history: Optional[List[Dict[str, Any]]] = None
) -> Union[str, ChatResponse]:
    """
    Sends query to Perplexica, which returns a structure with 'message' and 'sources'.
    """
    cleaned_query = clean_question_with_ollama(query)
    url = "http://localhost:3001/api/search"  # Adjust if needed

    payload = {
        "chatModel": {"provider": "ollama", "model": OLLAMA_MODEL},
        "embeddingModel": {"provider": "ollama", "model": OLLAMA_MODEL},
        "optimizationMode": "speed",
        "focusMode": "webSearch",
        "query": cleaned_query,
        "history": history or [],
    }

    try:
        print(f"[Perplexica] Sending request for query: {cleaned_query}")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers={"Content-Type": "application/json"}, json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"[Perplexica] HTTP error {response.status}: {error_text}")
                    return ChatResponse(error=f"HTTP error occurred: {response.status}")

                data = await response.json()
                print(f"[Perplexica] Received response: {json.dumps(data, indent=2)}")

                if not data or "message" not in data:
                    print("[Perplexica] Invalid response format")
                    return ChatResponse(error="Invalid response from AI service")

                # Extract the main text and format it
                message = data.get("message", "No message returned.")
                sources = data.get("sources", [])
                
                # Get the first source URL if available
                source_url = None
                if sources and len(sources) > 0 and "url" in sources[0]["metadata"]:
                    source_url = sources[0]["metadata"]["url"]
                
                # Format the response with source attribution if available
                formatted_response = format_qa_response(message, source_url)
                return ChatResponse(content=formatted_response)

    except aiohttp.ClientError as e:
        print(f"[Perplexica] Network error: {str(e)}")
        return ChatResponse(error=f"Network error: {str(e)}")
    except Exception as err:
        print(f"[Perplexica] Unexpected error: {str(err)}")
        traceback.print_exc()
        return ChatResponse(error=f"Unexpected error: {str(err)}")

# ----------------------------------------
# HIDEOUT COMMANDS
# ----------------------------------------
def get_cultist_help_response(question: str) -> str:
    # Delegates to implementation in cultist_help.py (logic moved out of main)
    return cultist_help_text(question)

@bot.tree.command(name="help", description="Get information about Cultist Circle timings and thresholds")
async def help(interaction: discord.Interaction, question: str):
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

@bot.tree.command(name="thresholds", description="Display Cultist Circle value thresholds and timing table")
async def thresholds(interaction: discord.Interaction):
    """Display a comprehensive table of Cultist Circle value thresholds and their corresponding timings."""
    table = get_thresholds_table()
    
    embed = discord.Embed(
        title="🕯️ Cultist Circle Thresholds",
        description=table,
        color=0x9b59b6,  # purple
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_footer(text="Cultist Calculator • Thresholds")
    
    await interaction.response.send_message(embed=embed, ephemeral=False)

# ----------------------------------------
# DISCORD BOT EVENTS
# ----------------------------------------
@bot.event
async def on_ready() -> None:
    print(f"{bot.user} has connected to Discord!")
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
