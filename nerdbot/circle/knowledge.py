"""Cultist Circle knowledge mirrored from https://cultistcircle.com.

Sources in the cultist-circle repo (update these together):
  app/faq/page.tsx                    -> FAQ
  components/hot-sacrifices-panel.tsx -> HOT_SACRIFICES
  config/excluded-items.ts            -> INCOMPATIBLE_ITEMS
  config/ritual-exclusions.ts         -> SIX_HOUR_EXCLUSIONS
  config/item-categories.ts           -> DEFAULT_EXCLUDED_CATEGORIES
"""

from __future__ import annotations

from dataclasses import dataclass

SITE = "https://cultistcircle.com"
FAQ_URL = f"{SITE}/faq"
RECIPES_URL = f"{SITE}/recipes"
DISCORD_INVITE = "https://discord.com/invite/3dFmr5qaJK"


@dataclass(frozen=True, slots=True)
class FaqEntry:
    id: str
    section: str
    question: str
    answer: str
    keywords: tuple[str, ...] = ()
    anchor: bool = True  # has a #anchor on the site

    @property
    def url(self) -> str:
        return f"{FAQ_URL}#{self.id}" if self.anchor else FAQ_URL


FAQ: tuple[FaqEntry, ...] = (
    FaqEntry(
        "how-to-use",
        "Calculator Guide",
        "How do I use the calculator?",
        "**1. Set a threshold** - pick your target, e.g. 400,000₽ for a shot at the 6h ritual.\n"
        "**2. Select items** - search and add items to the 5 ritual slots.\n"
        "**3. Check settings** - excluded categories and price preferences.\n"
        "**4. Auto Select** - let the app find the most cost-effective combination.\n\n"
        "**Pinning:** pin an item to force Auto Select to build around it. "
        "Great for things already sitting in your stash.",
        ("calculator", "how to use", "use the site", "auto select", "autoselect", "pin", "pinning",
         "pin item", "pin an item", "getting started", "guide", "tutorial"),
    ),
    FaqEntry(
        "item-hints",
        "Calculator Guide",
        "What are 'Item Hints'?",
        "Smart suggestions under empty slots, colour-coded to steer you towards items that "
        "get you to your current threshold efficiently.",
        ("item hints", "hints", "suggestions", "empty slot"),
    ),
    FaqEntry(
        "durations",
        "Ritual Mechanics",
        "How do ritual durations work?",
        "The timer tells you what kind of reward you get:\n"
        "**12 hours** - normal random loot. Sacrifices under 350,001₽.\n"
        "**14 hours** - high value loot. 350,001₽ to 399,999₽.\n"
        "**6 hours** - quest and hideout items. The one everyone wants.\n\n"
        "Lower totals give shorter timers with normal loot. Run `/thresholds` for the full table.",
        ("duration", "timer", "how long", "12h", "14h", "12 hour", "14 hour", "hours", "loot",
         "reward", "what do i get", "what does", "give", "get from", "ritual timer"),
    ),
    FaqEntry(
        "thresholds",
        "Ritual Mechanics",
        "What are the value thresholds for a 6h ritual?",
        "You need a total base value of **400,000₽ or more** for a chance at the 6 hour ritual.\n\n"
        "At 400k+ it's a **25% chance** of 6h and a **75% chance** of 14h. "
        "Going over 400k does **not** raise the 25%.",
        ("threshold", "400k", "400 000", "400000", "350k", "chance", "odds", "6h chance", "percent",
         "more value", "over 400", "need for 6h", "for 6h", "for a 6h", "6h ritual", "6 hour ritual",
         "for the 6 hour", "how much value", "value for", "need for", "increase the chance"),
    ),
    FaqEntry(
        "base-value",
        "Ritual Mechanics",
        "How is 'Base Value' calculated?",
        "The circle uses an internal base value, not flea or trader prices.\n"
        "```\nBase Value = Vendor Sell Price / Vendor Multiplier\n```"
        "Example: a Graphics Card sells to Therapist for 124,740₽ and her multiplier is 0.63, "
        "so 124,740 / 0.63 = **198,682₽**.\n\n"
        "Check any item with `/circle value`.",
        ("base value", "basevalue", "base price", "calculated", "calculate", "multiplier", "formula",
         "vendor", "how is value", "value work"),
    ),
    FaqEntry(
        "weapon-base-values",
        "Item & Category Issues",
        "Why do some weapons have such high Base Values?",
        "Weapon base values follow their trader sell prices, so rare or high tier guns like the "
        "**HK G28** are extremely efficient for reaching 400k.\n\n"
        "Attachments usually have low base values, and full builds are uncertain because "
        "durability and attached parts change the result.",
        ("weapon", "gun", "g28", "high base", "weapon value", "durability", "attachment", "mod",
         "worth so much", "gun worth", "worth", "so high"),
    ),
    FaqEntry(
        "categories",
        "Item & Category Issues",
        "Why are some items hidden in 'Excluded Categories'?",
        "In Settings you choose which categories you're willing to sacrifice. Unchecked "
        "categories are hidden from the calculator and Auto Select so you don't accidentally "
        "burn gear you want to keep.",
        ("excluded categories", "categories", "category", "hidden", "missing item", "cant find",
         "can't find", "not showing", "settings"),
    ),
    FaqEntry(
        "incompatible",
        "Item & Category Issues",
        "Why can't I use certain items in the ritual?",
        "Some items are hard-coded as **incompatible** with the circle. "
        "Ask me `can I sacrifice <item>` or see the Incompatible Items tab on the FAQ page.",
        ("incompatible", "can t use", "cant use", "not allowed", "won t accept", "wont accept",
         "doesn t accept", "rejected", "blocked", "can i sacrifice", "can i use", "use some item",
         "some item"),
    ),
    FaqEntry(
        "weapons-hidden",
        "Item & Category Issues",
        "Why are weapons hidden by default?",
        "Weapon base values are complex: they shift with durability and the exact parts "
        "attached. Turn them on under **Settings > Categories** if you have spares to burn.",
        ("weapons hidden", "weapon hidden", "no weapons", "enable weapons", "show weapons",
         "weapons default"),
    ),
    FaqEntry(
        "6h-exclusions",
        "Item & Category Issues",
        "Why are some items excluded from 6h rewards?",
        "Some high value items can be sacrificed but are **never returned** by a 6h ritual, "
        "which stops infinite loops of very rare items (think LedX). "
        "They can still drop from 14h rituals.",
        ("6h exclusions", "excluded", "never returned", "ledx", "returned", "loop", "6h reward",
         "blacklist", "come back", "come back from", "get back"),
    ),
    FaqEntry(
        "hot-sacrifices",
        "Item & Category Issues",
        "What are 'Hot Sacrifices'?",
        "Community-tested weapon combos that use special internal base values to hit 400k "
        "cheaply. Use the Hot Sacrifices panel on the site, or run `/circle hot` here.",
        ("hot sacrifices", "hot", "combos", "cheap 400k", "best combo", "mp5", "stm", "saiga",
         "popular", "meta", "recipe for 6h"),
    ),
    FaqEntry(
        "recipes",
        "Item & Category Issues",
        "What is the Recipes page?",
        f"A dedicated page with every known fixed recipe and its outcome: {RECIPES_URL}\n"
        "Some only work once per profile or have conditions. Search them with `/recipe`.",
        ("recipe", "figurine", "fixed reward", "guaranteed", "special recipe", "craft",
         "figurine give", "what do figurine"),
    ),
    FaqEntry(
        "optimization",
        "Tips & Tricks",
        "How can I optimize my sacrifices?",
        "**Exact thresholds** - aim just over 400,001₽. More value does not raise the 6h chance.\n"
        "**Check your quests** - have active quests for the best 6h results.\n"
        "**Stable prices** - red prices mean thin market data. Check in game first.\n"
        "**Best value vs low price** - settings let you price by last low or a weighted 24h average.",
        ("optimize", "optimise", "tips", "tricks", "strategy", "best way", "advice", "cheapest",
         "save money", "efficient", "quests"),
    ),
    # Bot and site extras that aren't on the FAQ page.
    FaqEntry(
        "red-price",
        "Tips & Tricks",
        "What do red or yellow prices mean?",
        "**Red** - the flea price is unstable (5 or fewer offers when it was captured).\n"
        "**Yellow** - you've overridden the price yourself.",
        ("red price", "yellow price", "price red", "price yellow", "red", "yellow", "unstable",
         "price colour", "price color", "override", "red text", "yellow text"),
        anchor=False,
    ),
    FaqEntry(
        "game-modes",
        "Calculator Guide",
        "Does it work for PvE and PvP?",
        "Yes. Switch between PvP and PvE (and the PvP season) so prices come from the right "
        "flea market. Here, most commands take a `mode` option.",
        ("pve", "pvp", "season", "mode", "game mode", "flea market", "which flea"),
        anchor=False,
    ),
    FaqEntry(
        "share",
        "Calculator Guide",
        "Can I share my selection?",
        "Yes. **Share** creates a compact code you can save or send to someone else.",
        ("share", "share code", "send", "save selection"),
        anchor=False,
    ),
    FaqEntry(
        "discord",
        "Community",
        "Is there a Discord?",
        f"Yep, come say hi: {DISCORD_INVITE}",
        ("discord", "community", "server", "support", "bug", "feedback", "report"),
        anchor=False,
    ),
)


@dataclass(frozen=True, slots=True)
class Ingredient:
    name: str  # exact tarkov.dev name, used for live pricing
    short: str
    count: int
    vendor: str = ""
    level: str = ""


@dataclass(frozen=True, slots=True)
class HotSacrifice:
    id: str
    ingredients: tuple[Ingredient, ...]
    result: str
    barter: bool = False  # first ingredient is bartered into the second
    disabled: bool = False
    featured: bool = False


_MP5 = "HK MP5 9x19 submachine gun (Navy 3 Round Burst) Default"
_MP5SD = "HK MP5 9x19 submachine gun (Navy 3 Round Burst) SD"
_STM = "Soyuz-TM STM-9 Gen.2 9x19 carbine Default"
_SAIGA = "Saiga-9 9x19 carbine Default"

HOT_SACRIFICES: tuple[HotSacrifice, ...] = (
    HotSacrifice("5x-mp5", (Ingredient(_MP5, "MP5", 5, "Peacekeeper", "LL1"),), "400K+ (6h & 14h)", featured=True),
    HotSacrifice(
        "4x-mp5-diary",
        (Ingredient(_MP5, "MP5", 4, "Peacekeeper", "LL1"), Ingredient("Diary", "Diary", 1)),
        "400K+ (6h & 14h)",
    ),
    HotSacrifice(
        "2x-mp5sd-diary",
        (Ingredient(_MP5SD, "MP5 SD", 2, "Peacekeeper", "LL2"), Ingredient("Diary", "Diary", 1)),
        "400K+ (6h & 14h)",
    ),
    HotSacrifice(
        "3x-stm-saiga",
        (Ingredient(_STM, "STM-9", 3, "Skier", "LL2"), Ingredient(_SAIGA, "Saiga-9", 1, "Skier", "LL1")),
        "350K+ (14h)",
    ),
    HotSacrifice(
        "4x-stm-saiga",
        (Ingredient(_STM, "STM-9", 4, "Skier", "LL2"), Ingredient(_SAIGA, "Saiga-9", 1, "Skier", "LL1")),
        "400K+ (6h & 14h)",
    ),
    HotSacrifice(
        "labs-g28",
        (
            Ingredient("TerraGroup Labs access keycard", "Labs Card", 1),
            Ingredient("HK G28 7.62x51 marksman rifle Patrol", "G28", 1, "Peacekeeper", "LL3"),
        ),
        "400K+ (6h & 14h)",
        barter=True,
    ),
    HotSacrifice(
        "sas-thor",
        (
            Ingredient("SAS drive", "SAS", 1),
            Ingredient("NFM THOR Integrated Carrier body armor", "THOR IC", 1, "Peacekeeper", "LL4"),
        ),
        "400K+ (6h & 14h)",
        barter=True,
        disabled=True,
    ),
)

# Items the circle refuses outright.
INCOMPATIBLE_ITEMS: frozenset[str] = frozenset({
    "26x75 mm flares cartridges", "Metal fuel tank", "Expeditionary fuel tank",
    "Roubles", "Dollars", "Euros", "GP coin",
    "Tripwire installation kit", "Vortes Ranger 1500 rangefinder", "Digital secure DSP radio transmitter",
    '"The Eye" mortar strike signaling device', "Mark of the unheard", "Radar station spare parts",
    "GARY ZONT portable electronic warfare device", "Sacred Amulet", "Signal Jammer",
    "KOSA UAV electronic jamming device",
    "Takedown sling backpack (MultiCam)", "Takedown sling backpack (Black)", "Blackjack 50", "Pilgrim",
    "SSO Attack 2 raid backpack (Khaki)", "6SH118 raid backpack", "Mystery Ranch SATL", "F4 Terminator",
    "Gunslinger II", "RUSH 100", "Santa's Bag",
    "RSP-30 reactive signal cartirdge (Blue)", "RSP-30 reactive signal cartridge (Special Yellow)",
    "RSP-30 reactive signal cartridge (Firework)",
    "Sealed box", "Contraband box", "Locked case", "Case key",
    "Christmas gift", "Small Christmas gift",
    "Key 01", "Key 02", "Key 03", "Key 04", "Labrys research notes",
    "Final Moment poster", "Taurus poster", "Tark Souls poster", "Last Breath poster",
    "Sealed weapon case", "Key case", "Thumb drive with military data", "Audio recorder",
    "Interchange underground utility plan", "Blank RFID keycard", "Reshala's bunkhouse key",
    "Zmeisky 3 apartment key", "Rus Post car key", "RB-PKPTS key", "TerraGroup corporate apartment key",
    "Elektronik's key", "Nut can", "SZ-1 explosive charge",
})

# Items a 6h ritual will never hand back. "LedX*" on the site is a prefix match.
SIX_HOUR_EXCLUSIONS: tuple[str, ...] = (
    "LEDX Skin Transilluminator",
    "Far-forward GPS Signal Amplifier Unit",
    "Advanced current converter",
)

# Categories the site leaves out of Auto Select by default.
DEFAULT_EXCLUDED_CATEGORIES: frozenset[str] = frozenset({
    "Ammo container", "Ammo", "Armor", "Armor Plate", "Armored equipment", "Chest rig", "Key",
    "Medical item", "Repair Kits", "Weapon",
})
