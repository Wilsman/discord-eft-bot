"""Cultist Circle knowledge mirrored from https://cultistcircle.com.

Sources in the cultist-circle repo (update these together):
  app/faq/page.tsx                    -> FAQ
  components/hot-sacrifices-panel.tsx -> HOT_SACRIFICES
  data/recipes.ts                     -> RECIPES
  config/excluded-items.ts            -> INCOMPATIBLE_ITEMS
  config/ritual-exclusions.ts         -> SIX_HOUR_EXCLUSIONS
  config/item-categories.ts           -> DEFAULT_EXCLUDED_CATEGORIES
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
        "Some only work once per profile or have conditions. Search them with `/circle recipes`.",
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


@dataclass(frozen=True, slots=True)
class Recipe:
    inputs: tuple[str, ...]
    time: str
    outputs: tuple[str, ...]
    note: str = ""
    pvp_only: bool = False
    repeatable: bool = False
    tags: frozenset[str] = field(default_factory=frozenset)


def _r(inputs, time, outputs, note="", **kw) -> Recipe:
    as_tuple = lambda v: (v,) if isinstance(v, str) else tuple(v)  # noqa: E731
    return Recipe(as_tuple(inputs), time, as_tuple(outputs), note, **kw)


RECIPES: tuple[Recipe, ...] = (
    _r("5x BD dogtag •| Ferrum", "5:55:55", "1x Briefcase with documents",
       "Launcher promo recipe. Reports say it may no longer work; only redeem-code BD dogtags ever did."),
    _r(["1x Christmas tree ornament (Silver)", "1x Christmas tree ornament (Red)", "1x Christmas tree ornament (Violet)"],
       "66 mins", "2x Ded Moroz figurine"),
    _r("1x Jaeger figurine", "66 mins", ["1x MTs-255-12 12ga shotgun", "1x Salty Dog beef sausage"]),
    _r("1x Lightkeeper figurine", "66 mins", "1x Sacred Amulet"),
    _r("1x Ragman figurine", "66 mins",
       ["Shemagh (Green)", "Round frame sunglasses", "RayBench Hipster Reserve sunglasses", "Ghost balaclava"],
       "Always 4 items from this pool, duplicates possible."),
    _r("1x BTR figurine", "66 mins", "1x OFZ 30x165mm shell"),
    _r("1x Hideout Cat figurine", "66 mins", "1x Cat figurine"),
    _r("1x Duck figurine", "66 mins", "5x Can of duck pate", pvp_only=True),
    _r("5x Can of duck pate", "66 mins", "1x Duck figurine"),
    _r("1x Labrys research notes", "66 mins", "1x Labrys access keycard"),
    _r("1x Elvisvista figurine", "66 mins", ["1x Elvisvista figurine", "1x Baseball cap"]),
    _r("1x Fence figurine", "66 mins", "3x Fence figurine"),
    _r("1x Mechanic figurine", "66 mins", ["2x Screw nuts", "1x Leatherman Multitool"]),
    _r("1x Peacekeeper figurine", "66 mins", ["2x MF-UNTAR body armor", "or 1x MF-UNTAR body armor + 1x UNTAR helmet"]),
    _r("1x Prapor figurine", "66 mins", "1x 42 Signature Blend English Tea"),
    _r("1x Skier figurine", "66 mins", ["1x Pompon hat", "1x Broken GPhone smartphone"]),
    _r("1x Therapist figurine", "66 mins", "1x Salewa first aid kit"),
    _r("1x Walking Tank figurine", "66 mins", ["2x BNTI Module-3M body armor", "2x Kalashnikov AK-74 5.45x39 assault rifle"]),
    _r("1x Mastichin figurine", "66 mins", ["1x Voron's Hideout key", "1x Note with code word Voron", "1x Raven"]),
    _r("1x 6-STEN-140-M military battery", "66 mins", "1x Old house toilet key",
       "The toilet key room has a 100% spawn for the 6-STEN-140-M battery."),
    _r("1x Domontovich ushanka hat", "66 mins",
       ["1x Supply department director's office key", "1x ZiD SP-81 26x75 signal pistol", "1x Bottle of Dan Jackiel whiskey"]),
    _r("1x Nut sack", "66 mins", ["SSh-68 helmet, BOSS cap, Ushanka and beanie mixes"], "Two known headwear outcomes."),
    _r("1x Christmas tree ornament (Red)", "66 mins", "1x Christmas tree ornament (Silver)"),
    _r("1x Christmas tree ornament (Silver)", "66 mins", "1x Christmas tree ornament (Violet)"),
    _r("1x Christmas tree ornament (Violet)", "66 mins", "1x Christmas tree ornament (Red)"),
    _r("1x Tigzresq splint", "66 mins", "1x Golden egg"),
    _r("1x Mazoni golden dumbbell", "66 mins", "1x Mazoni golden dumbbell"),
    _r("1x Augmentin antibiotic pills", "66 mins", "1x xTG-12 antidote injector"),
    _r("1x Pumpkin with sweets", "66 mins", "1x Jack-o'-lantern tactical pumpkin helmet"),
    _r("1x Jack-o'-lantern tactical pumpkin helmet", "66 mins", ["Random foods", "Random drinks"]),
    _r("1x WD-40 (400ml)", "66 mins", "WD-40 (100ml)"),
    _r("1x Bottle of water (0.6L)", "66 mins", "Fleece fabric"),
    _r(["1x Nailhead figurine", "1x Xenoalien figurine", "1x Pointy guy figurine", "1x Petya Crooker figurine",
        "1x Count Bloodsucker figurine"], "66 mins", "Tagilla's welding mask \"ZABEY\" (Replica)"),
    _r("1x Nailhead figurine", "66 mins", "Pack of nails"),
    _r("1x Xenoalien figurine", "66 mins", "Xenomorph sealing foam"),
    _r("1x Pointy guy figurine", "66 mins", "Rusty bloody key"),
    _r("1x Petya Crooker figurine", "66 mins", "Video cassette with the Cyborg Killer movie"),
    _r("1x Count Bloodsucker figurine", "66 mins", "Medical bloodset"),
    _r("Secure container Gamma (The Unheard Edition)", "6 mins", "Secure container Gamma (Edge of Darkness Edition)"),
    _r("Secure container Kappa", "66 mins", "Secure container Kappa (Desecrated)"),
    _r("1x Cultist figurine", "66 mins", "Spooky skull mask"),
    _r("5x Cultist figurine", "666 mins", "Cultist knife"),
    _r("Killa figurine", "66 mins", ["Maska-1SCh bulletproof helmet (Killa Edition)", "Maska-1SCh face shield (Killa Edition)"]),
    _r("Tagilla figurine", "66 mins", ["Tagilla's welding mask \"Gorilla\" or \"UBEY\""], "One mask, random."),
    _r("Reshala figurine", "66 mins", "TT-33 7.62x25 TT pistol (Golden)"),
    _r("Den figurine", "66 mins", ["Deadlyslob's beard oil", "Baddie's red beard"], "Always 2 items: oil and/or beard."),
    _r("Politician Mutkevich figurine", "66 mins", "3x Bottle of Tarkovskaya vodka"),
    _r("Scav figurine", "66 mins", ["Scav backpack", "Scav Vest"], "Always 2 items: backpack and/or vest."),
    _r("Ryzhy figurine", "66 mins", ["Obdolbos cocktail injector", "Pack of sugar"]),
    _r("BEAR operative figurine", "66 mins", "Grizzly medical kit"),
    _r("USEC operative figurine", "66 mins", "HighCom Trooper TFO body armor (MultiCam)"),
    _r("Mr Kerman's cat hologram", "66 mins", ["Mr Kerman's cat hologram", "TerraGroup Labs access keycard"]),
    _r("Ded Moroz figurine", "66 mins", "Santa's Bag"),
    _r("Relaxation room key", "66 mins", "Bottle of Fierce Hatchling moonshine"),
    _r("Dundukk sport sunglasses", "66 mins", "Axel parrot figurine"),
    _r("Soap", "66 mins", "Awl"),
    _r("Zarya stun grenade", "66 mins", "2x Light bulb"),
    _r("Physical Bitcoin", "666 mins", ["2x GreenBat lithium battery", "2x Tetriz portable game console"]),
    _r("LEDX Skin Transilluminator", "666 mins", "TerraGroup \"Blue Folders\" materials"),
    _r("1x Left half of a Physical Bitcoin", "666 seconds", "1x Right half of a Physical Bitcoin", repeatable=True),
    _r("1x Right half of a Physical Bitcoin", "666 seconds", "1x Left half of a Physical Bitcoin", repeatable=True),
    _r(["1x Left half of a Physical Bitcoin", "1x Right half of a Physical Bitcoin"], "666 seconds",
       "1x Physical Bitcoin", repeatable=True),
    _r("1x Secure container Gamma (Loui Peeton)", "66 mins", "1x Secure container Gamma (Loui Peeton)", repeatable=True),
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
