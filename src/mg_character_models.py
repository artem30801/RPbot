import collections
import enum
import functools
import inspect
import math
import operator
from typing import Dict, List, Optional, Union

from bson import ObjectId
from odmantic import EmbeddedModel, Field, Model, Reference


class Stat(str, enum.Enum):
    strength = "strength"
    agility = "agility"
    perception = "perception"
    intelligence = "intelligence"
    will = "will"
    build = "build"
    charisma = "charisma"
    luck = "luck"


class WeightStatus(str, enum.Enum):
    normal = "normal"
    overweight = "overweight"
    over_limit = "over limit"


def _override(a, b):
    return b


class OverrideMode(str, enum.Enum):
    ADD = "add", operator.add
    SUBTRACT = "subtract", operator.sub
    MULTIPLY = "multiply", operator.mul
    DIVIDE = "divide", operator.truediv
    OVERRIDE = "override", _override

    def __new__(cls, *args, **kwargs):
        obj = str.__new__(cls, args[0])
        obj._value_ = args[0]
        return obj

    # ignore the first param since it's already set by __new__
    def __init__(self, value, func=None):
        super().__init__()
        self._func = func

    @property
    def func(self):
        return self.func


class Player(Model):
    user_id: int
    current_character: Optional[ObjectId]

    is_gm: Optional[bool] = False


class ExtraStat(EmbeddedModel):
    name: str
    value: Union[int, float]
    hidden: bool


class StatOverride(EmbeddedModel):
    attr_name: str
    value: Union[int, float]
    mode: OverrideMode

    expire_time: Optional[int]


class Effect(EmbeddedModel):
    name: str
    description: Optional[str]
    overrides: List[StatOverride]


class Character(Model):
    player: Player = Reference()
    name: str = Field(max_length=25)
    level: int = Field(default=1, ge=0)

    current_hp: int = 0
    current_mp: int = 0
    current_stress: int = 0
    current_weight: int = 0
    action_points: int = 0

    luck_points: int = 0

    effects: List[Effect] = []
    extra_stats: List[ExtraStat] = []

    free_points: int = Field(default=15, ge=0)

    stats: Dict[str, int] = {stat: 10 for stat in Stat}

    def __str__(self):
        return f"{self.name} (lvl {self.level})"

    # @functools.cached_property
    # @property
    def all_overrides(self):
        overrides = collections.defaultdict(list)
        for effect in self.effects:
            for override in effect.overrides:
                overrides[override.attr_name].append(override)

        return overrides

    def get_attribute(self, name, use_overrides=True):
        value = self.__getattribute__(name)
        if use_overrides:
            overrides = self.all_overrides()[name]
            for override in overrides:
                value = override.mode.func(value, override.value)

        return math.ceil(value)

    def get_stat(self, stat):
        return self.stats[stat]

    def get_properties(self):
        properties = {
            name: self.get_attribute(name)
            for (name, value) in inspect.getmembers(
                Character, lambda v: isinstance(v, property)
            )
        }
        return properties

    @staticmethod
    def get_properties_diff(before, after):
        diff = {
            name: (a, b)
            for (name, a), (_, b) in zip(before.items(), after.items())
            if a != b
        }
        return diff

    def set_stat(self, stat, value):
        before = self.get_properties()

        self.stats[stat] = value

        after = self.get_properties()
        diff = self.get_properties_diff(before, after)
        return diff

    def get_stat_bonus(self, stat: Stat):
        return self.get_stat(stat) // 10

    def _regen(self, current_attr, max_attr, rate_attr, rounds=None):
        current = self.__getattribute__(current_attr)
        rate = self.get_attribute(rate_attr)
        max_value = self.get_attribute(max_attr)

        if rounds:
            regen = rate * rounds
        elif rate > 0:
            regen = self.get_attribute(max_attr) - current
        else:
            regen = 0

        new_value = min(self.get_attribute(max_attr), self.current_hp + regen)
        # self.s =

    def regen_hp(self, rounds=None):
        rate = self.get_attribute("hp_regen_rate")
        if rounds:
            regen = rate * rounds
        elif rate > 0:
            regen = self.get_attribute("max_hp") - self.current_hp
        else:
            regen = 0

        self.current_hp = min(self.get_attribute("max_hp"), self.current_hp + regen)

    def regen_mp(self, rounds=None):
        rate = self.get_attribute("mp_regen_rate")
        if rounds:
            regen = rate * rounds
        elif rate > 0:
            regen = self.get_attribute("max_mp") - self.current_mp
        else:
            regen = 0

        self.current_mp = min(self.get_attribute("max_mp"), self.current_mp + regen)

    @property
    def strength_bonus(self):
        return self.get_stat_bonus(Stat.strength)

    @property
    def agility_bonus(self):
        return self.get_stat_bonus(Stat.agility)

    @property
    def perception_bonus(self):
        return self.get_stat_bonus(Stat.perception)

    @property
    def intelligence_bonus(self):
        return self.get_stat_bonus(Stat.intelligence)

    @property
    def will_bonus(self):
        return self.get_stat_bonus(Stat.will)

    @property
    def build_bonus(self):
        return self.get_stat_bonus(Stat.build)

    @property
    def charisma_bonus(self):
        return self.get_stat_bonus(Stat.charisma)

    @property
    def luck_bonus(self):
        return self.get_stat_bonus(Stat.luck)

    @property
    def hp_regen_rate(self):
        # if self.level < 5:
        #     return 0
        regen = self.build_bonus * (self.level // 5)
        return math.ceil(regen)

    @property
    def mp_regen_rate(self):
        regen = (
            (self.intelligence_bonus + self.perception_bonus)
            / 2
            * (self.build_bonus / 2)
            * (self.level // 5 + 1)
        )
        return math.ceil(regen)

    @property
    def max_hp(self):
        return (
            self.get_stat(Stat.build) * (self.level // 5 + 1)
            + self.build_bonus * self.level
        )

    @property
    def max_mp(self):
        return (
            (self.get_stat(Stat.perception) + self.get_stat(Stat.intelligence))
            // 2
            * self.build_bonus
            * (self.level // 5 + 1)
        )

    @property
    def max_stress(self):
        return 20 * self.get_stat(Stat.will) * (
            self.level // 5 + 1
        ) + 20 * self.get_stat(Stat.will) * (self.level // 10)

    @property
    def max_action_points(self):
        return self.get_stat(Stat.will) * (self.level // 2 + 1)

    # Weight calculation

    @property
    def carry_weight(self):
        return self.get_stat(Stat.strength)

    @property
    def overweight_weight(self):
        return 2 * self.get_stat(Stat.strength)

    @property
    def max_weight(self):
        return 3 * self.get_stat(Stat.strength)

    @property
    def weight_status(self):
        if self.current_weight >= self.overweight_weight:
            return WeightStatus.overweight
        elif self.current_weight >= self.max_weight:
            return WeightStatus.over_limit
        else:
            return WeightStatus.normal

    # Speed calculation

    @property
    def walk_speed(self):
        speed = self.get_stat(Stat.agility)
        if self.current_weight >= self.overweight_weight:
            speed //= 2
        return speed

    @property
    def run_speed(self):
        return self.walk_speed * 2

    @property
    def run_speed(self):
        return self.walk_speed * 2

    @property
    def dash_speed(self):
        if self.current_weight >= self.overweight_weight:
            return 0
        return self.get_stat(Stat.agility) * 3


class Battle(Model):
    characters: List[ObjectId] = []
    current_character: Optional[ObjectId]


async def main():
    from odmantic import AIOEngine

    engine = AIOEngine()
    player = Player(
        user_id=12345,
    )
    char = Character(
        name="Pot2",
        player=player,
        effects=[
            Effect(
                name="potion",
                overrides=[
                    StatOverride(
                        attr_name="build_bonus", value=3, mode=OverrideMode.OVERRIDE
                    )
                ],
            )
        ],
    )
    print(char.doc())
    char.set_stat(Stat.build, 100)
    # print(OverrideMode.OVERRIDE.value)
    # print(OverrideMode.OVERRIDE.title())
    # await engine.save(char)


if __name__ == "__main__":
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
