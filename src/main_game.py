import asyncio
import datetime
import logging
import math
import random
import re

import discord
from bson import ObjectId
from discord.ext import commands
from discord_slash import ComponentContext, SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_choice, create_option
from discord_slash.utils.manage_components import (
    ButtonStyle,
    create_actionrow,
    create_button,
    create_select,
    create_select_option,
    wait_for_component,
)
from odmantic import AIOEngine

from src.mg_character_models import Character, Player, Stat
from src.utils.misc import guild_ids, make_progress_bar, make_table

logger = logging.getLogger(__name__)


class CharactersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db: AIOEngine = self.bot.db

    # async def update_options(self):
    #     pass

    async def get_character(self, ctx):
        player = await self.db.find_one(Player, Player.user_id == ctx.author.id)

        if player is None or not await self.db.count(
            Character, Character.player == player.id
        ):
            raise commands.BadArgument(
                "You don't have any characters! Use `/character create` to create character"
            )

        if player.current_character is None:
            raise commands.BadArgument(
                "No character was selected! Use `/character select` to select character to use"
            )

        character = await self.db.find_one(
            Character, Character.id == player.current_character
        )
        if character is None:
            player.current_character = None
            await self.db.save(player)
            raise commands.BadArgument("Sorry, this character does not exist anymore!")

        return player, character

    async def make_charsheet(self, ctx, player, character):
        embed = discord.Embed(color=discord.Color.blue())
        embed.title = f"{character}"
        embed.description = (
            f"Player: {ctx.guild.get_member(player.user_id).mention}\n"
            f"ID: ||{character.id}||"
        )

        stats = [
            [
                stat.title(),
                character.get_stat(stat),
                f"{character.get_stat_bonus(stat)} → {character.get_attribute(f'{stat}_bonus', True)}",
            ]
            for stat in Stat
        ]
        embed.add_field(
            name=f"Stats | free points: {character.free_points}",
            value=f"```py\n"
            f"{make_table(stats, labels=['Name', 'Value', 'Bonus'])}\n"
            f"```",
            inline=False,
        )

        width = 33

        bar_lines = [
            "```py",
            make_progress_bar(
                width,
                character.get_attribute("current_hp"),
                character.get_attribute("max_hp"),
                label=f"Health [regen: {character.get_attribute('hp_regen_rate')}]",
                unit="hp",
                checkpoints=[character.get_attribute("max_hp") // 4],
            ),
            make_progress_bar(
                width,
                character.get_attribute("current_mp"),
                character.get_attribute("max_mp"),
                label=f"Mana [regen: {character.get_attribute('mp_regen_rate')}]",
                unit="mp",
                style=" ◌○●",
            ),
            make_progress_bar(
                width,
                character.get_attribute("current_stress"),
                character.get_attribute("max_stress"),
                label="Stress",
                unit="sp",
                style=" ░▒▓",
                checkpoints=[
                    character.get_attribute("max_stress") * 10 // 20,
                    character.get_attribute("max_stress") * 15 // 20,
                    character.get_attribute("max_stress") * 18 // 20,
                ],
            ),
            make_progress_bar(
                width,
                character.get_attribute("current_weight"),
                character.get_attribute("max_weight"),
                label=f"Weight [{character.weight_status}]",
                unit="kg",
                checkpoints=[
                    character.get_attribute("carry_weight"),
                    character.get_attribute("overweight_weight"),
                ],
            ),
            "```",
        ]

        embed.add_field(
            name="Statuses",
            value="\n".join(bar_lines),
            inline=False,
        )

        weights = [
            ["Carry", character.get_attribute("carry_weight")],
            ["Overweight", character.get_attribute("overweight_weight")],
            ["Maximum", character.get_attribute("max_weight")],
        ]
        embed.add_field(
            name="Weight",
            value=f"```py\n" f"{make_table(weights)}" f"```",
        )

        speeds = [
            ["Walk", character.get_attribute("walk_speed")],
            ["Run", character.get_attribute("run_speed")],
            ["Dash", character.get_attribute("dash_speed")],
        ]
        embed.add_field(
            name="Movement speed",
            value=f"```py\n" f"{make_table(speeds)}" f"```",
        )

        embed.set_footer(text="Updated at")
        embed.timestamp = datetime.datetime.utcnow()

        return embed

    @cog_ext.cog_subcommand(base="character", name="info", guild_ids=guild_ids)
    async def info(self, ctx: SlashContext):
        """Displays charsheet with all stats and characteristics"""
        await ctx.defer()
        player, character = await self.get_character(ctx)
        embed = await self.make_charsheet(ctx, player, character)
        components = [
            create_actionrow(
                create_button(ButtonStyle.blue, "Refresh", "🔄", "refresh_charsheet")
            )
        ]

        await ctx.send(embed=embed, components=components)

    @cog_ext.cog_component()
    async def refresh_charsheet(self, ctx: ComponentContext):
        await ctx.defer(edit_origin=True)
        id_str = re.findall(r"\|\|(\w+)\|\|", ctx.origin_message.embeds[0].description)[
            0
        ]
        character_id = ObjectId(oid=id_str)
        character = await self.db.find_one(Character, Character.id == character_id)
        if character is None:
            await ctx.edit_origin(content="")
            raise commands.BadArgument("This character does not exist anymore!")

        embed = await self.make_charsheet(ctx, character.player, character)
        await ctx.edit_origin(embed=embed)

    @cog_ext.cog_subcommand(
        base="character",
        name="create",
        options=[
            create_option(
                name="name",
                description="Name of the new character",
                option_type=str,
                required=True,
            )
        ],
        guild_ids=guild_ids,
    )
    async def new_character(self, ctx: SlashContext, name):
        """Creates a new character"""
        await ctx.defer()
        player = await self.db.find_one(Player, Player.user_id == ctx.author.id)
        if player is None:
            player = Player(user_id=ctx.author.id)

        character = Character(name=name, player=player)
        await self.db.save(character)

        player.current_character = character.id
        await self.db.save(player)

        embed = discord.Embed(
            title="New character created", color=discord.Color.green()
        )
        embed.add_field(name="Character name", value=character.name)
        embed.add_field(name="Player", value=ctx.author.mention)
        embed.set_footer(text="Use `/character select` to select character to use")

        await ctx.send(embed=embed)

    @cog_ext.cog_subcommand(base="character", name="select", guild_ids=guild_ids)
    async def character_selector(self, ctx: SlashContext):
        """Sends a select menu to select your current character"""
        await ctx.defer(hidden=True)

        player = await self.db.find_one(Player, Player.user_id == ctx.author.id)

        if player is None or not await self.db.count(
            Character, Character.player == player
        ):
            await ctx.send(
                "Sorry, but you don't have any characters! Create one with `/character create`"
            )

        if player.is_gm:
            available_characters = await self.db.find(Character)
        else:
            available_characters = await self.db.find(
                Character, Character.player == player
            )

        component = create_actionrow(
            create_select(
                placeholder="Select a character to play with",
                custom_id="character_selected",
                min_values=1,
                max_values=1,
                options=[
                    create_select_option(
                        label=f"{character}",
                        value=character.id,
                    )
                    for character in available_characters
                ],
            )
        )

        await ctx.send(
            "Characters available to you:", components=[component], hidden=True
        )

    @cog_ext.cog_component()
    async def character_selected(self, ctx: ComponentContext):
        await ctx.defer(hidden=True)

        character_id = int(ctx.selected_options[0])
        player = await self.db.find_one(Player, Player.user_id == ctx.author.id)

        if player.is_gm:
            selected_character = await self.db.find_one(
                Character, Character.id == character_id
            )
        else:
            selected_character = await self.db.find_one(
                Character, Character.id == character_id, Character.player == player
            )

        if selected_character is None:
            raise commands.BadArgument("This character is not available!")

        player.selected_character = selected_character.id
        await self.db.save(player)
        await ctx.send(f"Successfully selected character: {selected_character}")

    @cog_ext.cog_subcommand(
        base="character",
        name="pointbuy",
        options=[
            create_option(
                name="stat",
                description="Stat to change for the character",
                option_type=str,
                required=True,
                choices=[
                    create_choice(name="Strength", value=Stat.strength),
                    create_choice(name="Agility", value=Stat.agility),
                    create_choice(name="Perception", value=Stat.perception),
                    create_choice(name="Intelligence", value=Stat.intelligence),
                    create_choice(name="Will", value=Stat.will),
                    create_choice(name="Build", value=Stat.build),
                    create_choice(name="Charisma", value=Stat.charisma),
                    create_choice(name="Luck", value=Stat.luck),
                ],
            ),
            create_option(
                name="value",
                description="Stat to change for the character",
                option_type=int,
                required=True,
            ),
            create_option(
                name="mode",
                description="Stat changing mode (default: add)",
                option_type=str,
                required=False,
                choices=[
                    create_choice(name="Add", value="add"),
                    create_choice(name="Subtract", value="sub"),
                    create_choice(name="Override value", value="new"),
                ],
            ),
        ],
        guild_ids=guild_ids,
    )
    async def pointbuy(self, ctx: SlashContext, stat: str, value, mode="add"):
        """Change stats of the character in point-buy manner"""
        await ctx.defer()

        player, character = await self.get_character(ctx)
        current_value = character.get_stat(stat)
        if mode == "new":
            new_value = value
        elif mode == "add":
            new_value = current_value + value
        elif mode == "sub":
            new_value = current_value - value
        else:
            raise ValueError

        if new_value < 10:
            raise commands.BadArgument(f"{stat.title()} value must be at least 10!")

        delta = current_value - new_value
        character.free_points += delta
        if character.free_points < 0:
            raise commands.BadArgument(
                f"Not enough stat points to perform operation!\n"
                f"You miss {-character.free_points} stat points"
            )

        diff = character.set_stat(stat, new_value)
        await self.db.save(character)

        embed = discord.Embed(
            title=f"{character} changed stats",
            color=discord.Color.green() if delta < 0 else discord.Color.red(),
        )
        embed.add_field(
            name="Points",
            value=f"{'Spent' if delta < 0 else 'Gained'} **{abs(delta)}** stat points\n"
            f"**{character.free_points}** free points left",
            inline=False,
        )
        embed.add_field(
            name=stat.title(),
            value=f"**{current_value}** → **{new_value}**",
            inline=False,
        )
        if diff:
            derived_stats = [
                [f"{name.title().replace('_', ' ')}:", f"{a: >2} → {b: >2}"]
                for name, (a, b) in diff.items()
            ]

            embed.add_field(
                name="Derived characteristics",
                # value="\n".join([f"*{name.title().replace('_', ' ')}:* **{a}** → **{b}**" for name, (a, b) in diff.items()])
                value=f"```py\n" f"{make_table(derived_stats)}" f"```",
            )

        await ctx.send(embed=embed)

    @cog_ext.cog_slash(
        name="regen",
        options=[
            create_option(
                name="rounds",
                description="Amount of rounds to regen",
                option_type=int,
                required=False,
            ),
            create_option(
                name="full",
                description="Whether to regenerate fully",
                option_type=bool,
                required=False,
            ),
            create_option(
                name="type",
                description="What to regen",
                option_type=str,
                required=False,
                choices=[
                    create_choice(name="All", value="all"),
                    create_choice(name="Health", value="health"),
                    create_choice(name="Mana", value="mana"),
                ],
            ),
        ],
        connector={"type": "regen_type"},
        guild_ids=guild_ids,
    )
    async def regen(self, ctx: SlashContext, rounds=None, full=False, regen_type="all"):
        if rounds and full:
            raise commands.BadArgument(
                "You can't use both 'rounds' and 'full=True' arguments"
            )
        await ctx.defer()

        rounds = None if full else (rounds or 1)

        player, character = await self.get_character(ctx)
        regen_types = ["health", "mana"] if regen_type == "all" else [regen_type]

        embed = discord.Embed(color=discord.Color.green())
        embed.title = f"{character} regenerated!"
        total_rounds = 0

        if "health" in regen_types:
            old_health = character.current_hp
            character.regen_hp(rounds)
            hp_regened = character.current_hp - old_health
            total = (
                f"**{old_health}** hp → **{character.current_hp}** hp"
                if hp_regened
                else f"**{character.current_hp}** hp"
            )
            embed.add_field(
                name=f"Health regenerated: {hp_regened}", value=f"Total: {total}"
            )
            if character.hp_regen_rate:
                total_rounds = max(
                    total_rounds, math.ceil(hp_regened / character.hp_regen_rate)
                )

        if "mana" in regen_types:
            old_mana = character.current_mp
            character.regen_mp(rounds)
            mp_regened = character.current_mp - old_mana
            total = (
                f"**{old_mana}** mp → **{character.current_mp}** mp"
                if mp_regened
                else f"**{character.current_mp}** mp"
            )
            embed.add_field(
                name=f"Mana restored: {mp_regened}", value=f"Total: {total}"
            )
            if character.mp_regen_rate:
                total_rounds = max(
                    total_rounds, math.ceil(mp_regened / character.mp_regen_rate)
                )

        embed.description = (
            f"For {total_rounds} rounds (minutes)"
            if total_rounds
            else "Nothing was regenerated tho"
        )
        await self.db.save(character)
        await ctx.send(embed=embed)

    @cog_ext.cog_subcommand(
        base="roll",
        name="stat",
        options=[
            create_option(
                name="stat",
                description="Stat to perform roll on",
                option_type=str,
                required=True,
                choices=[
                    create_choice(name="Strength", value=Stat.strength),
                    create_choice(name="Agility", value=Stat.agility),
                    create_choice(name="Perception", value=Stat.perception),
                    create_choice(name="Intelligence", value=Stat.intelligence),
                    create_choice(name="Will", value=Stat.will),
                    create_choice(name="Build", value=Stat.build),
                    create_choice(name="Charisma", value=Stat.charisma),
                    create_choice(name="Luck", value=Stat.luck),
                ],
            ),
            create_option(
                name="modifier",
                description="GM-provided roll modifier",
                option_type=int,
                required=False,
            ),
        ],
        guild_ids=guild_ids,
    )
    async def roll(self, ctx: SlashContext, stat: str, modifier=0):
        await ctx.defer()
        player, character = await self.get_character(ctx)

        stat_value = character.get_stat(stat)
        difficulty = min(99, max(1, stat_value + modifier))
        roll = random.randint(1, 100)
        success = roll <= difficulty
        success_level = max(1, math.ceil(abs(roll - difficulty) / 10))
        if not success:
            success_level *= -1

        color = discord.Color.green() if success else discord.Color.red()
        embed = discord.Embed(color=color)
        embed.title = f"{character} {stat} roll"
        embed.description = (
            f"Modifier: **{modifier}**\n"
            f"{stat.title()}: **{stat_value}**\n"
            f"Success threshold: **<= {difficulty}**"
        )
        embed.add_field(
            name=("Success!" if success else "Fail!"),
            value=f"Roll result: **{roll}**\n" f"Success level: **{success_level}**",
        )

        row = create_actionrow(
            create_button(
                ButtonStyle.blue,
                "Use luck to improve roll",
                disabled=(character.luck_points > 0),
            )
        )
        await ctx.send(embed=embed, components=[row])

        async def callback(button_ctx: ComponentContext):
            if button_ctx.author != ctx.author:
                await button_ctx.send(
                    "Sorry, but it's not your decision to make!", hidden=True
                )
                return False

            _, btn_character = await self.get_character(ctx)
            if btn_character.luck_points <= 0:
                pass

            await button_ctx.defer(edit_origin=True)

            pass

        async def button_processor():
            while True:
                button_ctx = await wait_for_component(self.bot)
                do_exit = await callback(button_ctx)
                if do_exit:
                    return

        await asyncio.wait_for(button_processor(), timeout=10*60)

    @cog_ext.cog_subcommand(
        base="character",
        name="change",
        options=[
            create_option(
                name="stat",
                description="Stat to change for the character",
                option_type=str,
                required=True,
                choices=[
                    create_choice(name="Health", value="health"),
                    create_choice(name="Mana", value="mana"),
                    create_choice(name="Stress", value="stress"),
                    create_choice(name="Weight", value="weight"),
                ],
            ),
            create_option(
                name="value",
                description="Stat to change for the character",
                option_type=int,
                required=True,
            ),
            create_option(
                name="mode",
                description="Stat changing mode (default: add)",
                option_type=str,
                required=False,
                choices=[
                    create_choice(name="Override value", value="new"),
                    create_choice(name="Add", value="add"),
                    create_choice(name="Subtract", value="sub"),
                ],
            ),
        ],
        guild_ids=guild_ids,
    )
    async def change_status(self):
        pass


def setup(bot):
    bot.add_cog(CharactersCog(bot))
