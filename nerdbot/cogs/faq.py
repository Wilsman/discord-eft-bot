from __future__ import annotations

import re
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from .. import __version__, style
from ..circle import faq
from ..circle.knowledge import FAQ_URL, SITE, FaqEntry
from ..circle.tiers import tier_for
from ..views import Reply, link_view

if TYPE_CHECKING:
    from ..bot import NerdBot

ENTRY_PREFIX = "faq:"


def entry_reply(entry: FaqEntry, related: tuple[FaqEntry, ...] = ()) -> Reply:
    e = style.embed(entry.question, entry.answer, url=entry.url, color=style.ACCENT)
    if related:
        e.add_field(name="Related", value="\n".join(f"[{r.question}]({r.url})" for r in related[:3]), inline=False)
    style.footer(e, "cultistcircle.com/faq", entry.section)
    return {"embed": e, "view": link_view(("Read on cultistcircle.com", entry.url))}


def not_sure_reply(question: str, suggestions: tuple[FaqEntry, ...]) -> Reply:
    lines = "\n".join(f"[{s.question}]({s.url})" for s in suggestions[:4])
    e = style.embed(
        "Not sure about that one",
        f"I couldn't match **{style.truncate(question, 120)}** to the FAQ.\n\nMaybe one of these?\n{lines}",
        color=style.MUTED,
    )
    e.add_field(
        name="Other things I can do",
        value="`/price` item prices  ·  `/circle cheapest` best combo  ·  `/thresholds` timer chart",
        inline=False,
    )
    return {"embed": e, "view": link_view(("Browse the FAQ", FAQ_URL))}


class Faq(commands.Cog):
    def __init__(self, bot: NerdBot) -> None:
        self.bot = bot
        self._mention_cooldown = commands.CooldownMapping.from_cooldown(3, 30, commands.BucketType.user)

    def answer(self, question: str) -> Reply:
        question = question.strip()
        if question.startswith(ENTRY_PREFIX):
            entry = faq.entry_by_id(question[len(ENTRY_PREFIX):])
            if entry:
                return entry_reply(entry)

        subject = faq.sacrifice_subject(question)
        if subject:
            return self._sacrifice_reply(subject)

        if faq.mentions_six_hour_reward(question):
            excluded = faq.six_hour_mentioned(question)
            if excluded:
                e = style.embed(
                    f"{excluded} never comes from a 6h",
                    f"**{excluded}** is on the 6h exclusion list: you can sacrifice it, but a 6 hour ritual "
                    "will never hand it back. It can still drop from 14h rituals.",
                    color=style.WARN,
                    url=f"{FAQ_URL}#6h-exclusions",
                )
                return {"embed": style.footer(e, "cultistcircle.com/faq")}

        result = faq.ask(question)
        if result.entry is None:
            return not_sure_reply(question, result.related)
        return entry_reply(result.entry, result.related)

    def _sacrifice_reply(self, subject: str) -> Reply:
        blocked = faq.incompatible_match(subject)
        if blocked:
            e = style.embed(
                f"No, {blocked} won't work",
                f"**{blocked}** is on the incompatible list, so the circle won't accept it.",
                color=style.BAD,
                url=f"{FAQ_URL}#incompatible",
            )
            return {"embed": style.footer(e, "cultistcircle.com/faq")}

        catalog = self.bot.store.peek("regular") if self.bot.store else None
        item = None
        if catalog:
            item, _ = catalog.index.resolve(subject)
        if item is None:
            e = style.embed(
                "Probably, yes",
                f"**{style.truncate(subject, 80)}** isn't on the incompatible list. "
                "Most items work; check its base value with `/circle value`.",
                color=style.MUTED,
            )
            return {"embed": e}
        lines = [f"**{item.name}** isn't on the incompatible list, so it's fair game."]
        lines.append(f"Base value **{item.base:,}** ({tier_for(item.base).hours} on its own).")
        if faq.six_hour_excluded(item.name):
            lines.append("Note: it's on the 6h exclusion list, so a 6h ritual will never return it.")
        if item.is_weapon:
            lines.append("It's a weapon, so the real circle value can differ from base value.")
        e = style.embed(f"Yes, {item.name} works", "\n".join(lines), color=style.GOOD, url=item.link)
        if item.image:
            e.set_thumbnail(url=item.image)
        return {"embed": style.footer(e, "tarkov.dev", "cultistcircle.com")}

    # ------------------------------------------------------------ slash

    @app_commands.command(name="faq", description="Ask anything about the Cultist Circle")
    @app_commands.describe(question="Pick a common question or type your own")
    async def faq_command(self, interaction: discord.Interaction, question: str) -> None:
        await interaction.response.send_message(**self.answer(question))

    @faq_command.autocomplete("question")
    async def _faq_questions(self, interaction: discord.Interaction, current: str):
        choices = [
            app_commands.Choice(name=style.truncate(e.question, 100), value=f"{ENTRY_PREFIX}{e.id}")
            for e in faq.search_questions(current, limit=24)
        ]
        if current.strip() and not any(c.name.lower() == current.lower() for c in choices):
            # Let people send their own wording as-is.
            choices.insert(0, app_commands.Choice(name=style.truncate(f"Ask: {current}", 100), value=current[:100]))
        return choices[:25]

    @app_commands.command(name="help", description="What NerdBot can do")
    async def help_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=self.help_embed(), view=link_view(("Cultist Circle", SITE)))

    def help_embed(self) -> discord.Embed:
        p = self.bot.settings.prefix
        e = style.embed(
            "NerdBot",
            "Tarkov market data and Cultist Circle help, live from tarkov.dev and cultistcircle.com. "
            "Most commands take a `mode` option for PvP, PvE or the PvP season.",
        )
        e.add_field(
            name="Cultist Circle",
            value=(
                "`/thresholds` timer chart, add a total to see where it lands\n"
                "`/circle cheapest` cheapest combo for 400k or 350k\n"
                "`/circle check` total up your own combo\n"
                "`/circle value` one item's base value by copies\n"
                "`/circle hot` community-tested weapon combos\n"
                "`/circle recipes` figurines and other fixed recipes"
            ),
            inline=False,
        )
        e.add_field(name="Market", value="`/price` flea, trader and base value\n`/ammo` ballistics and caliber lineup", inline=False)
        e.add_field(
            name="Questions",
            value="`/faq` anything about the circle\nor just @mention me with a question",
            inline=False,
        )
        e.add_field(name="Game", value="`/status` EFT servers  ·  `/bosses` latest boss spawn changes", inline=False)
        e.add_field(
            name="Quick commands",
            value=f"`{p}thresholds [total]`  `{p}price <item> [pve]`  `{p}hot`  `{p}faq <question>`  `{p}help`",
            inline=False,
        )
        return style.footer(e, f"NerdBot v{__version__}")

    # ------------------------------------------------------------ prefix

    @commands.command(name="faq", aliases=["ask", "q"])
    @commands.cooldown(3, 15, commands.BucketType.user)
    async def faq_prefix(self, ctx: commands.Context, *, question: str = "") -> None:
        """!faq <question>"""
        if not question.strip():
            await ctx.reply(mention_author=False, **not_sure_reply("(nothing)", tuple(faq.search_questions("", 4))))
            return
        await ctx.reply(mention_author=False, **self.answer(question))

    @commands.command(name="help", aliases=["commands"])
    @commands.cooldown(2, 15, commands.BucketType.channel)
    async def help_prefix(self, ctx: commands.Context) -> None:
        await ctx.reply(embed=self.help_embed(), view=link_view(("Cultist Circle", SITE)), mention_author=False)

    # ------------------------------------------------------------ @mention

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        me = self.bot.user
        if message.author.bot or me is None or me not in message.mentions:
            return
        if message.content.startswith(self.bot.settings.prefix):
            return
        text = re.sub(rf"<@!?{me.id}>", "", message.content).strip()
        if not text:
            await message.reply(embed=self.help_embed(), mention_author=False)
            return
        bucket = self._mention_cooldown.get_bucket(message)
        if bucket and bucket.update_rate_limit():
            return
        async with message.channel.typing():
            reply = self.answer(text)
        await message.reply(mention_author=False, **reply)


async def setup(bot: NerdBot) -> None:
    await bot.add_cog(Faq(bot))
