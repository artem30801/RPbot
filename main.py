import asyncio

# import nest_asyncio_apply  # We want to apply nested asyncio as early as we can, so we do it in this import
import json
import logging
import os
import random
from datetime import datetime

import discord
from discord.ext import commands
from discord_slash import SlashCommand
from odmantic import AIOEngine

import src.utils.misc as utils


class RPbot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.slash = SlashCommand(self, sync_commands=False)
        self.db = AIOEngine()

        current_dir = os.path.dirname(os.path.realpath(__file__))
        os.chdir(current_dir)

        random.seed()

        self.token = None

        self.config = {}
        self.load_config("config.json")

        self.initial_extensions = []

    def load_config(self, path):
        with open(utils.abs_join(path), "r") as f:
            self.config = json.load(f)

        self.owner_ids = set(self.config["discord"]["owner_ids"])
        utils.guild_ids = self.config["discord"]["guild_ids"]
        self.token = self.config["auth"]["discord_token"]

    def load_initial_extensions(self, extensions):
        for name in extensions:
            self.initial_extensions.append(name)
            try:
                super().load_extension(name)
            except Exception as error:
                logging.critical(
                    f"Error during loading extension {name}: {repr(error)}",
                    exc_info=error,
                )

    async def start(self):
        await super().start(self.token)


async def main():
    intents = discord.Intents.default()
    intents.members = True
    bot = RPbot(
        command_prefix=commands.when_mentioned_or("$", "!"),
        help_command=None,
        case_insensitive=True,
        intents=intents,
    )

    @bot.command()
    async def sync(ctx):
        await bot.slash.sync_all_commands()
        await ctx.send("Syncing all slash commands")

    # noinspection PyArgumentList
    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(asctime)s] [%(levelname)-9.9s]-[%(name)-15.15s]: %(message)s",
    )
    logging.getLogger("db_client").setLevel(logging.INFO)
    logging.getLogger("aiomysql").setLevel(logging.INFO)
    logging.getLogger("discord.client").setLevel(logging.CRITICAL)
    logging.getLogger("discord.gateway").setLevel(logging.ERROR)
    logging.getLogger("discord.http").setLevel(logging.ERROR)

    initial_extensions = ["src.errors", "src.main_game"]

    bot.load_initial_extensions(initial_extensions)

    try:
        await bot.start()
    finally:
        await bot.logout()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
