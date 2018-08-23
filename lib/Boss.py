from StaticData import Map, Location
from characters import Character
import random
import codecs
import json
import os
from enum import Enum


class Boss(object):
    class State(Enum):
        PASSIVE = "PASSIVE"
        DEAD = "DEAD"
        ATTACKING = "ATTACKING"
        RAGE = "RAGE"

    def __init__(self, boss_id, name, state, hp, attack, defense, x, y, respawn_time, hp_regen, connection):
        self._boss_id = boss_id
        self.name = name
        self.connection = connection
        self.hp = hp
        self._max_hp = hp
        self.state = self.State(state)
        self._attack_bonus = attack
        self._defense_bonus = defense
        self.lvl = 1
        self._x = x
        self._y = y
        self.respawn_time = respawn_time
        self.hp_regen = hp_regen

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def attack_bonus(self):
        return self._attack_bonus

    @property
    def defense_bonus(self):
        return self._defense_bonus

    def damage(self, value):
        self.hp -= value
        if self.hp <= 0:
            self.state = self.State.DEAD

    def attack(self):
        targets = Character.find_by_location(*(Map.boss_location()))
        if len(targets) == 0:
            self.state = self.State.PASSIVE
            self.hp = self._max_hp
        target = random.choice(targets)
        if self.attack_target(target) or self.attack_target(target):
            self.hp += self.hp_regen
            pass  # TODO: kill target

    def attack_target(self, target):
        roll = random.randint(1, 40)
        armor_bonus = target.trait.defense_bonus()
        if target.armor is not None:
            armor_bonus += target.armor.min_lvl
        return roll + self.lvl * 2 + self.attack_bonus > \
               target.lvl * 2 + armor_bonus + 20

    @classmethod
    def find_by_name(cls, name, connection):
        cursor = connection.execute(
            """SELECT * from bosses
            WHERE name = :name""",
            {"name": name}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def create_bosses(cls, connection):
        """creates bosses into the database"""
        bosses = cls.read_bosses()
        connection.executemany("""INSERT OR IGNORE INTO bosses(name, attack, defense, max_hp, hp, x, y, hp_regen)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", bosses)
        connection.commit()

    @staticmethod
    def read_bosses():
        path = os.path.join(os.path.split(os.path.dirname(__file__))[0], "data\Bosses.json")
        with codecs.open(path, encoding="utf-8-sig", mode="r") as f:
            return json.load(f, encoding="utf-8")

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute(
            """create table if not exists bosses
            (boss_id        integer PRIMARY KEY NOT NULL,
            name            text    UNIQUE      NOT NULL,
            state           text    NOT NULL    default 'PASSIVE',
            lvl             integer NOT NULL    default 1,
            attack          integer NOT NULL,
            defense         integer NOT NULL,
            max_hp          text    NOT NULL,
            hp              text    NOT NULL,
            respawn_time    timestamp,
            x               integer NOT NULL,
            y               integer NOT NULL,
            hp_regen        integer NOT NULL    default 0
            );"""
        )
