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
import datetime
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

@bot.tree.command(name="cultist", description="Search for optimal cultist circle items to sacrifice")
@app_commands.describe(
    tags="Item tags to filter by (default: barter-item)",
    threshold="Minimum price threshold in roubles (default: 400000)",
    max_items="Maximum number of items to show (default: 5)"
)
async def cultist(
    interaction: discord.Interaction, 
    tags: str = "barter-item", 
    threshold: int = 400000, 
    max_items: int = 5
):
    await interaction.response.defer()
    data = await fetch_cultist_data(tags, threshold, max_items)
    response = format_cultist_response(data)
    await interaction.followup.send(response)

@bot.tree.command(name="price", description="Search for item prices")
@app_commands.describe(
    item_name="Name of the item to search for"
)
async def price(interaction: discord.Interaction, item_name: str):
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

    # Parse timestamps
    current_dt = datetime.now(tz.utc)
    pvp_dt = datetime.fromisoformat(item["updated"].replace("Z", "+00:00"))
    pvp_mins = int((current_dt - pvp_dt).total_seconds() / 60)
    
    # Format time strings
    def format_time(mins: Optional[int]) -> str:
        if mins is None:
            return "N/A"
        hours = mins // 60
        minutes = mins % 60
        return f"{hours}h{minutes}m" if hours > 0 else f"{minutes}m"

    # Create embed
    embed = discord.Embed(
        title=item["name"],
        description=item.get("description", "No description available"),
        color=0x2b2d31  # Dark theme color
    )
    
    # Add thumbnail if available
    if "iconLink" in item:
        embed.set_thumbnail(url=item["iconLink"])
    
    # Add PvP price field
    pvp_price = item.get('price')
    if pvp_price is not None:
        embed.add_field(
            name="💰 PvP Price",
            value=f"{pvp_price:,}₽\nUpdated {format_time(pvp_mins)} ago",
            inline=True
        )
    else:
        embed.add_field(
            name="💰 PvP Price",
            value="Not available",
            inline=True
        )
    
    # Add PvE price field if available
    pve_price = item.get('pvePrice')
    pve_updated = item.get('pveUpdated')
    if pve_price is not None and pve_updated:
        pve_dt = datetime.fromisoformat(pve_updated.replace("Z", "+00:00"))
        pve_mins = int((current_dt - pve_dt).total_seconds() / 60)
        embed.add_field(
            name="🤖 PvE Price",
            value=f"{pve_price:,}₽\nUpdated {format_time(pve_mins)} ago",
            inline=True
        )
    else:
        embed.add_field(
            name="🤖 PvE Price",
            value="Not available",
            inline=True
        )
    
    # Add trader info if available
    trader_price = item.get('traderSellPrice')
    if trader_price is not None:
        trader_info = (
            f"{trader_price:,}₽\n"
            f"to {item.get('traderSellName', 'Unknown Trader')}"
        )
        embed.add_field(
            name="🏪 Trader Sell Price",
            value=trader_info,
            inline=True
        )
    else:
        embed.add_field(
            name="🏪 Trader Sell Price",
            value="Not available",
            inline=True
        )
    
    # Add extra info
    extra_info = []
    base_price = item.get('basePrice')
    if base_price is not None:
        extra_info.append(f"Base Price: {base_price:,}₽")
    if "width" in item and "height" in item:
        extra_info.append(f"Size: {item['width']}x{item['height']}")
    if extra_info:
        embed.add_field(
            name="ℹ️ Additional Info",
            value="\n".join(extra_info),
            inline=False
        )
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="ai", description="Ask AI a Question")
@app_commands.describe(
    question="Your question to the ai"
)
async def ai_search(
    interaction: discord.Interaction, 
    question: str
):
    await interaction.response.defer()
    
    try:
        # Add time context to the question
        time_context = format_time_context()
        context_message = create_chat_prompt(question, time_context)
        
        # Search using Perplexica
        response = await search_perplexica(context_message)
        
        # Handle the response
        if isinstance(response, ChatResponse):
            if response.error:
                await interaction.followup.send(f"Error: {response.error}")
            else:
                # Truncate response if it's too long
                content = response.content
                if len(content) > 1900:  # Leave room for ellipsis and source
                    # Find the last complete sentence before the limit
                    last_period = content[:1900].rfind('.')
                    if last_period == -1:
                        last_period = 1900
                    content = content[:last_period + 1] + "\n\n[Response truncated due to length...]"
                await interaction.followup.send(content)
        else:
            # For backward compatibility with string responses
            content = str(response)
            if len(content) > 1900:
                content = content[:1900] + "\n\n[Response truncated due to length...]"
            await interaction.followup.send(content)
            
    except Exception as e:
        error_message = f"An error occurred while processing your question: {str(e)}"
        await interaction.followup.send(error_message)

@bot.tree.command(name="ammo", description="Look up information about ammunition types")
async def ammo(interaction: discord.Interaction, name: str):
    """Look up information about ammunition types"""
    await interaction.response.defer()
    
    ammo_info = get_ammo_info(name)
    if ammo_info is None:
        error_embed = discord.Embed(
            title="Ammo Not Found",
            description=f"No ammunition found matching '{name}'",
            color=0xFF0000
        )
        await interaction.followup.send(embed=error_embed)
        return
        
    proper_name, category, damage, pen = ammo_info
    ammo_embed = format_ammo_embed(proper_name, category, damage, pen)
    
    await interaction.followup.send(embed=ammo_embed)

# ----------------------------------------
# AMMO FUNCTIONS
# ----------------------------------------
from typing import Optional, Tuple, Union
from ammo_data import AMMO_DATA

def get_ammo_info(ammo_name: str) -> Optional[Tuple[str, str, Union[str, int], int]]:
    """
    Get category, damage and penetration values for given ammo type
    Returns tuple of (proper_name, category, damage, penetration) or None if ammo not found
    """
    # Try exact match first
    ammo_name = ammo_name.upper()
    if ammo_name in AMMO_DATA:
        return ammo_name, *AMMO_DATA[ammo_name]
    
    # Try partial matches
    matches = [name for name in AMMO_DATA.keys() if ammo_name in name]
    if matches:
        return matches[0], *AMMO_DATA[matches[0]]
    
    return None

def get_pen_color(pen: int) -> int:
    """Get color based on penetration value"""
    if pen >= 50:  # High pen (red)
        return 0xFF0000
    elif pen >= 30:  # Medium pen (orange)
        return 0xFFA500
    elif pen >= 20:  # Low-medium pen (yellow)
        return 0xFFFF00
    else:  # Low pen (green)
        return 0x00FF00

def format_ammo_embed(ammo_name: str, category: str, damage: Union[str, int], pen: int) -> discord.Embed:
    """Format ammo information into a Discord embed"""
    embed = discord.Embed(
        title=ammo_name.title(),
        color=get_pen_color(pen)
    )
    
    embed.add_field(name="Category", value=category, inline=False)
    
    # Handle damage formatting
    if isinstance(damage, str) and 'x' in damage:
        pellets, dmg = damage.split('x')
        total_damage = int(pellets) * int(dmg)
        damage_str = f"{damage} ({total_damage} total)"
        embed.add_field(name="Damage Per Pellet", value=dmg, inline=True)
        embed.add_field(name="Pellet Count", value=pellets, inline=True)
        embed.add_field(name="Total Damage", value=str(total_damage), inline=True)
    else:
        embed.add_field(name="Damage", value=str(damage), inline=True)
        embed.add_field(name="", value="", inline=True)  # Empty field for alignment
    
    embed.add_field(name="Penetration", value=str(pen), inline=True)
    
    # Add footer with pen level description
    if pen >= 50:
        pen_desc = "High penetration - Effective against high-tier armor"
    elif pen >= 30:
        pen_desc = "Medium penetration - Effective against medium-tier armor"
    elif pen >= 20:
        pen_desc = "Low-medium penetration - Effective against low-tier armor"
    else:
        pen_desc = "Low penetration - Best used against unarmored targets"
    
    embed.set_footer(text=pen_desc)
    
    return embed

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
    q = question.lower().strip()

    def in_q(*terms: str) -> bool:
        return any(t in q for t in terms)

    # Thresholds and durations
    if in_q("6h", "6 h", "6-hour", "six hour"):
        return "6h chance requires ≥400k base value. At ≥400k: 25% 6h, 75% 14h. Going over 400k doesn't increase the chance."
    elif in_q("14h", "14 h", "better loot"):
        return "≥350k gives a chance at 14h. At 350–399k: 12h/14h mix. At ≥400k: 75% 14h (and 25% 6h)."
    elif in_q("12h", "12 h", "default"):
        return "12h is the default. <350k is guaranteed 12h; 350–399k can give 12h or 14h."

    # Threshold summary
    elif in_q("threshold", "thresholds", "explain thresholds"):
        return "Thresholds: <350k → 12h. 350–399k → 12h/14h. ≥400k → 25% 6h, 75% 14h. Over 400k doesn't improve 6h chance."

    # Base value calculation
    elif in_q("base value", "multiplier", "vendor"):
        return "Base value = vendor sell price ÷ vendor trading multiplier (avoid Fence). Example: 126,000 ÷ 0.63 = 200,000."

    # Examples
    elif in_q("moonshine"):
        return "Moonshine base value: 126,000 ÷ 0.63 = 200,000. Two bottles reach 400k (6h/14h pool)."
    elif in_q("vase", "antique"):
        return "Antique Vase: 33,222 ÷ 0.49 ≈ 67,800. Five = ~339k (12h). 1 Moonshine + 3 Vases ≈ 403.4k (6h/14h pool)."

    # Item count rule
    elif in_q("how many", "how much", "items", "slots"):
        return "You can place 1–5 items in the circle. Any mix is fine as long as total base value hits your target threshold."

    # Weapon-specific behavior and example combos
    elif in_q("weapon", "weapons", "gun"):
        if in_q("investigating") or ("higher" in q and "base" in q):
            return "We're investigating why some weapons return higher base values in the circle; weapon-specific values may apply."
        else:
            return "Weapons have special circle values; vendor-base math may not apply. Durability can affect value, so totals can differ."
    elif in_q("durability"):
        return "Item durability can influence effective circle value, especially for weapons."
    elif in_q("mp5sd", "slim diary"):
        return "Reported combo: 2× MP5SD (~$900 total from Peacekeeper) + 1× Slim Diary (~40–50k₽) can reach the 400k threshold due to weapon-specific values."
    elif in_q("flash drive"):
        return "Flash Drive may be a cheaper alternative to Slim Diary depending on market; try 2× MP5SD + Diary/Flash Drive."
    elif in_q("5x mp5", "5 x mp5", "five mp5", "mp5"):
        return "Reported combo: 5× MP5 (Peacekeeper L1) can trigger 6/14h due to special weapon circle values."
    elif in_q("g28", "labs access", "labs card"):
        return "Reported combo: 1× G28 Patrol Rifle via barter (1 Labs Access Card, ~166k from Therapist) can trigger 6/14h due to special weapon values."

    # Features from Instructions
    elif in_q("auto select", "autoselect"):
        return "Auto Select finds the most cost-effective combo to hit your target (e.g., ≥400k) automatically."
    elif in_q("pin"):
        return "Pin locks chosen items so Auto Select must include them in the final combination."
    elif in_q("override"):
        return "Override lets you set custom flea prices when market differs from API data."
    elif in_q("share"):
        return "Share creates a compact code to save or send your selection to others."
    elif in_q("red price", "unstable"):
        return "Red price text = unstable flea price (low offer count at capture)."
    elif in_q("yellow price", "manual"):
        return "Yellow price text = price manually overridden by you."
    elif in_q("exclude", "categories"):
        return "Exclude categories you don't want to sacrifice to narrow results."
    elif in_q("sort"):
        return "Sort items by most recently updated or best value for rubles."

    # PVP flea status and trader pricing
    elif ("pvp" in q and "flea" in q) or in_q("flea disabled", "flea off"):
        return "PVP: Flea is disabled. Use Settings → Price Mode: Trader, then set Trader Levels to calculate trader-only prices."
    elif in_q("trader price", "price mode", "trader levels"):
        return "Switch Price Mode to Trader in Settings, then pick your Trader Levels (LL1–LL4) to use trader-only prices."
    elif in_q("hardcore", "l1 traders", "ll1") or ("level 1" in q and "trader" in q):
        return "Hardcore PVP tip (LL1): 5× MP5 from Peacekeeper ≈ 400k+. Cost: $478 (~63,547₽) × 5 = $2,390 (~317,735₽)."
    elif in_q("limitation", "wip", "work in progress", "quest locked"):
        return "Trader pricing is work-in-progress: quest-locked items are currently included."
    elif in_q("mode", "pve", "pvp"):
        return "Toggle PVE/PVP to match the correct flea market for pricing/search."
    elif in_q("tips", "strategy", "optimal"):
        return "Aim slightly over 400k, use Auto Select, pin items you own, and ensure relevant quests are active for quest rewards."
    elif in_q("discord", "discord server", "discord community"):
        return "Join our Discord server for support, updates, and community discussion. https://discord.com/invite/3dFmr5qaJK"

    # Calculator usage
    elif in_q("calculator", "how to use", "use it", "help"):
        return "Pick up to 5 items and check total base value: ≥350k for 14h chance; ≥400k for 25% 6h / 75% 14h. Base value uses vendor price ÷ multiplier."

    # Default
    return (
        "Ask about thresholds (350k/400k), 6h/12h/14h chances, base value math (vendor ÷ trader multiplier), "
        "PVE/PVP flea, item combos, Auto Select/Pin/Override/Share/Refresh, price indicators, excluding categories, sorting, tips, or Discord."
    )

@bot.tree.command(name="help", description="Get information about Scav Case timings and thresholds")
async def help(interaction: discord.Interaction, question: str):
    """
    Get information about Scav Case timings and thresholds
    
    Example questions:
    - "6h chance"
    - "14h loot"
    - "base value calculation"
    - "moonshine example"
    - "weapon values"
    - "thresholds"
    - "hardcore tips"
    """
    response = get_cultist_help_response(question)
    
    await interaction.response.send_message(response, ephemeral=False)

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
