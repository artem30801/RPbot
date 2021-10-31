import asyncio

from discord_slash.utils import manage_commands


async def main():
    await manage_commands.remove_all_commands_in(
        bot_id=865266625317830737,
        bot_token="ODY1MjY2NjI1MzE3ODMwNzM3.YPBgVw.V-Ujj5UqdtIVXHmhRc-vtDqYfjw",
    )


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
