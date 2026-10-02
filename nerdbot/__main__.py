from __future__ import annotations

import logging

from .bot import NerdBot
from .config import load_settings


def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    NerdBot(settings).run(settings.token, log_handler=None)


if __name__ == "__main__":
    main()
