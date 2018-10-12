from characters import Character
import random
import codecs
import json
import os
from enum import Enum
from pytz import utc
import datetime as dt
from Position import Position


class Boss(object):
    class State(Enum):
        PASSIVE = "PASSIVE"
        DEAD = "DEAD"
        ATTACKING = "ATTACKING"
        RAGE = "RAGE"

    def __init__(self, boss_id, name, state, lvl, attack, defense, max_hp, hp, respawn_time, x, y, hp_regen,
                 next_attack, connection):
        self._boss_id = boss_id
        self.name = name
        self.connection = connection
        self.hp = hp
        self._max_hp = max_hp
        self.state = self.State(state)
        self._attack_bonus = attack
        self._defense_bonus = defense
        self.lvl = lvl
        self._x = x
        self._y = y
        self.position = Position(x, y)
        self.respawn_time = respawn_time
        self.hp_regen = hp_regen
        self.next_attack = next_attack

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

    @property
    def boss_id(self):
        return self._boss_id

    @property
    def max_hp(self):
        return self._max_hp

    def damage(self, value):
        self.hp -= value
        if self.state is self.State.PASSIVE:
            self.state = self.State.ATTACKING
            self.next_attack = dt.datetime.now(utc)
        if 0 < self.hp <= self._max_hp/4:
            self.state = self.State.RAGE
        if self.hp <= 0:
            self.state = self.State.DEAD
            self.respawn_time = dt.datetime.now(utc) + dt.timedelta(hours=1)
            return True
        return False

    def do_attack(self, fight_time):
        self.next_attack += dt.timedelta(seconds=fight_time)
        targets = Character.find_by_location(self.x, self.y, connection=self.connection)
        if len(targets) == 0:
            self.state = self.State.PASSIVE
            self.hp = self._max_hp
            self.lvl += 1
            return
        target = random.choice(targets)
        if self.attack_target(target) or self.attack_target(target):
            self.hp += self.hp_regen
            return target

    def attack_target(self, target):
        roll = random.randint(1, 40)
        armor_bonus = target.trait.defense_bonus
        if target.armor is not None:
            armor_bonus += target.armor.min_lvl
        return roll + self.lvl * 2 + self.attack_bonus > \
               target.lvl * 2 + armor_bonus + 20

    def save(self):
        self.connection.execute(
            """UPDATE bosses set name = :name, boss_id = :boss_id, state = :state, lvl = :lvl, attack = :attack,
            defense = :defense, max_hp = :max_hp, hp = :hp, respawn_time = :respawn_time, x = :x, y = :y,
            hp_regen = :hp_regen, next_attack = :next_attack""",
            {"name": self.name, "boss_id": self.boss_id, "state": self.state.value, "lvl": self.lvl,
             "attack": self.attack_bonus, "defense": self.defense_bonus, "max_hp": self._max_hp, "hp": self.hp,
             "respawn_time": self.respawn_time, "x": self.x, "y": self.y, "hp_regen": self.hp_regen,
             "next_attack": self.next_attack}
        )

    @classmethod
    def respawn_bosses(cls, conn):
        for boss in cls.find_need_respawn(conn):
            boss.state = boss.State.PASSIVE
            boss.respawn_time = None
            boss.lvl = 1
            boss.hp = boss.max_hp
            boss.save()

    @classmethod
    def find(cls, boss_id, connection):
        cursor = connection.execute(
            """SELECT * from bosses
            WHERE boss_id = :boss_id""",
            {"boss_id": boss_id}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

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
    def find_by_active_and_past_attack_time(cls, connection):
        cursor = connection.execute(
            """SELECT * from bosses
            WHERE state in ('ATTACKING', 'RAGE') and next_attack <= :now""",
            {"now": dt.datetime.now(utc)}
        )
        return map(lambda row: cls(*row, connection=connection), cursor)

    @classmethod
    def find_need_respawn(cls, connection):
        cursor = connection.execute(
            """SELECT * from bosses
            WHERE state in ('DEAD') and respawn_time <= :now""",
            {"now": dt.datetime.now(utc)}
        )
        return map(lambda row: cls(*row, connection=connection), cursor)

    @classmethod
    def create_bosses(cls, connection):
        """creates bosses into the database"""
        bosses = cls.read_bosses()
        connection.executemany("""INSERT OR IGNORE INTO bosses(name, attack, defense, max_hp, hp, x, y, hp_regen)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", bosses)

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
            max_hp          integer    NOT NULL,
            hp              integer    NOT NULL,
            respawn_time    timestamp,
            x               integer NOT NULL,
            y               integer NOT NULL,
            hp_regen        integer NOT NULL    default 0,
            next_attack     timestamp
            );"""
        )
