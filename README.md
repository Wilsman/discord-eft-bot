# NerdBot

Escape from Tarkov market data and Cultist Circle help for Discord. Prices come live from
[tarkov.dev's JSON API](https://json.tarkov.dev/endpoints); circle rules, FAQ, hot
sacrifices and recipes mirror [cultistcircle.com](https://cultistcircle.com).

## Commands

| Command | What it does |
| --- | --- |
| `/thresholds [total]` | The circle value to timer chart as an image. Add a total to highlight where it lands. |
| `/circle cheapest` | Cheapest combo for 400k or 350k. Flea or trader prices, trader level, weapons on/off, and an `own` item to build around. |
| `/circle check <combo>` | Total up a combo like `2x moonshine + 1 graphics card`. |
| `/circle value <item>` | Base value for 1 to 5 copies and the timer each lands on. |
| `/circle hot` | Community-tested weapon combos with live cost estimates. |
| `/circle recipes [search]` | Fixed-outcome recipes (figurines, keys and so on). |
| `/faq <question>` | Answers from the Cultist Circle FAQ. @mentioning the bot with a question works too. |
| `/price <item>` | Flea, 24h average, trader buy and sell, per slot, base value. |
| `/ammo <round>` | Ballistics plus the full caliber lineup by penetration. |
| `/status`, `/bosses` | EFT server status and the latest boss spawn changes. |

Quick prefix versions: `!thresholds [total]`, `!price <item> [pve]`, `!hot`, `!faq <question>`, `!help`.
Most slash commands take a `mode` option: PvP, PvE or PvP Season.

The **Message Content** intent must be enabled for the bot in the Discord developer
portal for `!` commands and @mention questions.

## Running locally

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # .venv/bin/pip on Linux/macOS
cp .env.example .env                                # then fill in DISCORD_TOKEN
.venv/Scripts/python -m nerdbot
.venv/Scripts/python -m pytest
```

Set `DEV_GUILD_ID` in `.env` to sync slash commands instantly to one test server.
Global sync happens only when the command definitions actually change.

## How it works

- `nerdbot/tarkov` fetches `/{mode}/items`, `items_en` and `traders` from json.tarkov.dev,
  keeps only the fields the bot uses (about 40 MB per mode in memory), and refreshes every
  15 minutes with ETags so unchanged data costs a 304.
  PvP and PvE load at startup; PvP Season loads on first use.
- `nerdbot/circle` holds the tiers, the optimizer (Pareto pruning plus a bounded
  knapsack, verified against brute force), the FAQ matcher and the thresholds card renderer.
- `nerdbot/cogs` are the Discord commands.

### Keeping circle knowledge in sync

`nerdbot/circle/knowledge.py` and `nerdbot/circle/tiers.py` mirror files in the
cultist-circle repo (paths are listed at the top of each file). Update them together.
`tests/test_faq.py` holds real questions and the answer each should get, so add a case when
you add an entry.

Regenerate the trimmed test data with `python tests/make_fixture.py`.

## Hosting

One Lightsail nano instance (512 MB, USD 5/month flat, IPv4 included), defined in
`deploy/lightsail.yaml`. Discord has no IPv6 endpoint, so the cheaper IPv6-only bundle
can't work. See [deploy/README.md](deploy/README.md).
