import enum
import logging
import math

from tortoise import fields
from tortoise.models import Model

logger = logging.getLogger(__name__)


class Player(Model):
    id = fields.IntField(pk=True)
    user_id = fields.BigIntField(unique=True)

    characters: fields.ReverseRelation["Character"]
    current_character = fields.IntField(null=True)

    gm = fields.BooleanField(default=False)


class Character(Model):
    id = fields.IntField(pk=True)
    player = fields.ForeignKeyField(
        "models.Player",
        related_name="characters",
    )

    name = fields.CharField(unique=True, max_length=25)
    level = fields.IntField(default=1)

    current_hp = fields.IntField(default=0)
    current_mp = fields.IntField(default=0)
    current_stress = fields.IntField(default=0)
    current_weight = fields.IntField(default=0)

    max_hp_bonus = fields.IntField(default=0)
    max_mp_bonus = fields.IntField(default=0)

    hp_regen_modifier = fields.FloatField(default=1)
    mp_regen_modifier = fields.FloatField(default=1)

    action_points = fields.IntField(default=15)
    stunned = fields.BooleanField(default=False)

    free_points = fields.IntField(default=0)

    strength = fields.IntField(default=10)
    agility = fields.IntField(default=10)
    perception = fields.IntField(default=10)
    intelligence = fields.IntField(default=10)
    will = fields.IntField(default=10)
    build = fields.IntField(default=10)
    charisma = fields.IntField(default=10)
    luck = fields.IntField(default=10)

    strength_extra = fields.IntField(default=0)
    agility_extra = fields.IntField(default=0)
    perception_extra = fields.IntField(default=0)
    intelligence_extra = fields.IntField(default=0)
    will_extra = fields.IntField(default=0)
    build_extra = fields.IntField(default=0)
    charisma_extra = fields.IntField(default=0)
    luck_extra = fields.IntField(default=0)

    extra_stats: fields.ReverseRelation["ExtraStats"]

    def __str__(self):
        return f"{self.name} (lvl {self.level})"

    @property
    def hp_regen_rate(self):
        # if self.level < 5:
        #     return 0
        regen = self.build_bonus * (self.level // 5)
        return math.ceil(regen * self.hp_regen_modifier)

    @property
    def mp_regen_rate(self):
        regen = (
            (self.intelligence_bonus + self.perception_bonus)
            / 2
            * (self.build_bonus / 2)
            * (self.level // 5 + 1)
        )
        return math.ceil(regen * self.mp_regen_modifier)

    @property
    def max_hp(self):
        return (
            self.build * (self.level // 5 + 1)
            + self.build_bonus * self.level
            + self.max_hp_bonus
        )

    @property
    def max_mp(self):
        return (self.perception + self.intelligence) // 2 * self.build_bonus * (
            self.level // 5 + 1
        ) + self.max_mp_bonus

    @property
    def max_stress(self):
        return 20 * self.will * (self.level // 5 + 1) + 20 * self.will * (
            self.level // 10
        )

    @property
    def max_action_points(self):
        return self.agility_bonus * (self.level // 2 + 1)

    # Weight calculation

    @property
    def carry_weight(self):
        return self.strength

    @property
    def overweight_weight(self):
        return 2 * self.strength

    @property
    def max_weight(self):
        return 3 * self.strength

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
        speed = self.agility
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
        return self.agility * 3

    # Stat bonuses calculation

    @property
    def strength_bonus(self):
        return self.get_bonus(Stats.strength, False)

    @property
    def agility_bonus(self):
        return self.get_bonus(Stats.agility, False)

    @property
    def perception_bonus(self):
        return self.get_bonus(Stats.perception, False)

    @property
    def intelligence_bonus(self):
        return self.get_bonus(Stats.intelligence, False)

    @property
    def will_bonus(self):
        return self.get_bonus(Stats.will, False)

    @property
    def build_bonus(self):
        return self.get_bonus(Stats.build, False)

    @property
    def charisma_bonus(self):
        return self.get_bonus(Stats.charisma, False)

    @property
    def luck_bonus(self):
        return self.get_bonus(Stats.luck, False)

    def regen_hp(self, rounds=None):
        if rounds:
            regen = self.hp_regen_rate * rounds
        elif self.hp_regen_rate > 0:
            regen = self.max_hp - self.current_hp
        else:
            regen = 0

        self.current_hp = min(self.max_hp, self.current_hp + regen)

    def regen_mp(self, rounds=None):
        if rounds:
            regen = self.mp_regen_rate * rounds
        elif self.mp_regen_rate > 0:
            regen = self.max_mp - self.current_mp
        else:
            regen = 0

        self.current_mp = min(self.max_mp, self.current_mp + regen)

    def get_bonus(self, stat, add_extra=True):
        value = self.__getattribute__(stat) // 10
        if add_extra:
            value += self.__getattribute__(f"{stat}_extra")
        return value

    def get_stat(self, stat):
        value = self.__getattribute__(stat)
        return value

    def set_stat(self, stat, value):
        cascade = []
        self.__setattr__(stat, value)

        return cascade

    def _strength_cascade(self):
        pass


class ExtraStats(Model):
    id = fields.IntField(pk=True)

    character = fields.ForeignKeyField("models.Character", related_name="extra_stats")

    name = fields.TextField()
    value = fields.IntField()
    hidden = fields.BooleanField(default=False)
