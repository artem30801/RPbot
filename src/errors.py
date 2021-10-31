import logging

import discord
from discord.ext import commands
from discord_slash import SlashContext
from tortoise import exceptions as t_exceptions

logger = logging.getLogger(__name__)


class Errors(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_slash_command_error(self, ctx: SlashContext, error):
        if isinstance(error, commands.CommandOnCooldown):
            message = f"Heyo! Not so fast! Try {ctx.command} again in {error.retry_after:.2f}s"
        elif isinstance(error, commands.BadArgument):
            message = f"Sorry, but your arguments are invalid: {' ,'.join(error.args)}"
        elif isinstance(error, commands.MissingRequiredArgument):
            message = (
                f"Sorry, but you missed required argument! {' ,'.join(error.args)}"
            )
        elif isinstance(error, commands.CheckFailure):
            message = "\n".join(error.args)
        elif isinstance(error, commands.NoPrivateMessage):
            message = "You can use that only in guild!"
        elif isinstance(error, t_exceptions.ValidationError):
            message = f"Sorry, but your arguments are invalid: {' ,'.join(error.args)}"
        elif isinstance(error, t_exceptions.IntegrityError):
            message = f"Sorry, but your arguments are invalid: {error.args[0].args[1]}"
        elif isinstance(error, t_exceptions.OperationalError):
            logger.error(f"Database error {repr(error)} occurred:", exc_info=error)
            await ctx.channel.send("Database connection error, please retry!")
            return
        else:
            logger.error(f"Unexpected error {repr(error)} occurred:", exc_info=error)
            return

        await ctx.send(
            message, hidden=True, allowed_mentions=discord.AllowedMentions.none()
        )


def setup(bot):
    bot.add_cog(Errors(bot))
