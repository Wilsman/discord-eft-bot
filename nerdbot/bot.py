from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from . import __version__, style
from .config import Settings
from .tarkov import TarkovStore

log = logging.getLogger("nerdbot")

EXTENSIONS = (
    "nerdbot.cogs.market",
    "nerdbot.cogs.circle",
    "nerdbot.cogs.faq",
    "nerdbot.cogs.game",
)
SYNC_STAMP = Path(__file__).resolve().parent.parent / ".command-sync"


class DataUnavailable(app_commands.AppCommandError):
    pass


class NerdBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.message_content = True  # needed for !commands and @mention questions
        super().__init__(
            command_prefix=settings.prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.settings = settings
        self.session: aiohttp.ClientSession | None = None
        self.store: TarkovStore | None = None
        self.tree.on_error = self.on_app_command_error

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()
        self.store = TarkovStore(self.session, self.settings.json_api)
        for mode in ("regular", "pve"):
            try:
                await self.store.get(mode)
            except Exception:
                log.exception("Initial %s load failed; will retry on refresh", mode)
        for ext in EXTENSIONS:
            await self.load_extension(ext)
        await self._sync_commands()
        self.refresh_data.change_interval(minutes=self.settings.refresh_minutes)
        self.refresh_data.start()

    async def _sync_commands(self) -> None:
        guild = discord.Object(self.settings.dev_guild_id) if self.settings.dev_guild_id else None
        if guild:
            self.tree.copy_global_to(guild=guild)
        payload = json.dumps(
            [c.to_dict(self.tree) for c in self.tree.get_commands(guild=guild)], sort_keys=True
        )
        digest = hashlib.sha256(f"{guild and guild.id}:{payload}".encode()).hexdigest()
        if SYNC_STAMP.exists() and SYNC_STAMP.read_text().strip() == digest:
            log.info("Slash commands unchanged; skipping sync")
            return
        synced = await self.tree.sync(guild=guild)
        SYNC_STAMP.write_text(digest)
        log.info("Synced %d slash commands%s", len(synced), f" to guild {guild.id}" if guild else "")

    async def close(self) -> None:
        self.refresh_data.cancel()
        if self.session:
            await self.session.close()
        await super().close()

    async def on_ready(self) -> None:
        log.info("Ready as %s (v%s) in %d guild(s)", self.user, __version__, len(self.guilds))
        await self._update_presence()

    async def _update_presence(self) -> None:
        catalog = self.store.peek("regular") if self.store else None
        text = f"/help  ·  {len(catalog.items):,} items tracked" if catalog else "/help"
        await self.change_presence(activity=discord.CustomActivity(name=text))

    @tasks.loop(minutes=15)
    async def refresh_data(self) -> None:
        assert self.store is not None
        modes = self.store.loaded_modes or ["regular", "pve"]
        for mode in modes:
            try:
                if mode in self.store.loaded_modes:
                    await self.store.refresh(mode)
                else:
                    await self.store.get(mode)
            except Exception:
                log.exception("Refreshing %s failed; keeping the previous data", mode)
        if self.is_ready():
            await self._update_presence()

    @refresh_data.before_loop
    async def _before_refresh(self) -> None:
        await self.wait_until_ready()

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        original = getattr(error, "original", error)
        if isinstance(error, app_commands.CommandOnCooldown):
            message = f"Give it {error.retry_after:.0f}s and try again."
        elif isinstance(original, DataUnavailable):
            message = str(original)
        elif isinstance(original, (aiohttp.ClientError, TimeoutError)):
            message = "Couldn't reach tarkov.dev just now. Try again in a minute."
        else:
            log.exception("Command %s failed", interaction.command and interaction.command.name, exc_info=original)
            message = "Something broke on my end. It's been logged."
        embed = style.error(message)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException:
            pass

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(f"Easy, give it {error.retry_after:.0f}s.", mention_author=False)
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(f"Usage: `{ctx.clean_prefix}{ctx.command.qualified_name} {ctx.command.signature}`", mention_author=False)
            return
        log.exception("Prefix command %s failed", ctx.command, exc_info=error)
        await ctx.reply(embed=style.error("Something broke on my end. It's been logged."), mention_author=False)
