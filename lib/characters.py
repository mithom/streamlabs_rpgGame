from StaticData import Location, Weapon, Armor, StaticData
from Bounty import Bounty
import random
from enum import Enum
from pytz import utc
import datetime as dt


class Character(object):
    """
    by default lazy load static data, this is in memory anyway
    """
    game = None

    def __init__(self, char_id, name, user_id, experience, lvl, location_id, weapon_id, armor_id, trait_id,
                 exp_gain_time, connection, location=None, weapon=None, armor=None, trait=None, special_ids=None,
                 specials=None):
        if special_ids is None:
            special_ids = []
        if specials is None:
            specials = []
        self.__char_id = char_id
        self.name = name
        self.user_id = user_id
        self.experience = experience
        self.lvl = lvl
        if exp_gain_time.tzinfo is None:
            exp_gain_time = utc.localize(exp_gain_time)
        self.exp_gain_time = exp_gain_time

        self.location_id = location_id
        self._location = location

        self.weapon_id = weapon_id
        self._weapon = weapon

        self.armor_id = armor_id
        self._armor = armor

        self.trait_id = trait_id  # This is a string
        self._trait = trait

        self.special_ids = special_ids  # This is a string
        self._specials = specials

        self.connection = connection

    @property
    def char_id(self):
        return self.__char_id

    @property
    def location(self):
        if self._location is None:
            self._location = Location.find(self.location_id)
        return self._location

    @location.setter
    def location(self, location):
        self._location = location
        self.location_id = location.id

    @property
    def weapon(self):
        if self._weapon is None and self.weapon_id is not None:
            self._weapon = Weapon.find(self.weapon_id)
        return self._weapon

    @weapon.setter
    def weapon(self, weapon):
        self._weapon = weapon
        self.weapon_id = weapon.id

    @property
    def armor(self):
        if self._armor is None and self.armor_id is not None:
            self._armor = Armor.find(self.armor_id)
        return self._armor

    @armor.setter
    def armor(self, armor):
        self._armor = armor
        self.armor_id = armor.id

    @property
    def trait(self):
        if self._trait is None:
            self._trait = Trait.find(self.trait_id)
        return self._trait

    @trait.setter
    def trait(self, trait):
        self._trait = trait
        self.trait_id = trait.id

    def attempt_flee(self):
        if random.random()*100 <= 45:
            self.location = Location.find_by_name("Town")  # TODO: random locatie
            self.save()

    def exp_for_difficulty(self, difficulty):
        weapon_bonus = 0
        if self.weapon is not None:
            weapon_bonus = self.weapon.min_lvl*10
        return int(25 * (2 ** (0.7 * (difficulty - self.lvl) + 1))*(100+weapon_bonus)/100.0)

    def exp_for_next_lvl(self):
        return int(100 + ((2.8 * self.lvl) ** 2))

    def gain_experience(self, xp):
        """gain experience, auto lvl-up
        :return True if lvl'ed up, False otherwise"""
        self.experience += xp
        next_lvl_exp = self.exp_for_next_lvl()
        if self.experience >= next_lvl_exp:
            self.experience -= next_lvl_exp
            self.lvl += 1
            return True
        return False

    def check_survival(self):
        rand = random.random()*100
        armor_bonus = 0
        if self.armor is not None:
            armor_bonus = self.armor.min_lvl*10
        if self.location.difficulty < self.lvl:
            return rand > 100 * (4 + 0.5 * (self.location.difficulty - self.lvl)) / (100 + armor_bonus)
        return rand > 100*(4 + 1.5*(self.location.difficulty - self.lvl))/(100.0+armor_bonus)

    def attack(self, defender, defense_bonus=False, attack_bonus=False):
        roll = random.randint(1, 40)
        weapon_bonus = 0
        armor_bonus = 0
        if self.weapon is not None:
            weapon_bonus = self.weapon.min_lvl
        if defender.armor is not None:
            armor_bonus = defender.armor.min_lvl
        return roll + self.lvl * 2 + weapon_bonus + (attack_bonus * 2) >\
               defender.lvl * 2 + armor_bonus + 20 + (defense_bonus * 2)

    def add_kill(self):
        pie_bounty = Bounty.find_by_character_name_from_piebank(self.name, self.connection)
        if pie_bounty is None:
            Bounty.create(self, None, 0, 1, self.connection)
        else:
            pie_bounty.kill_count += 1

    def save(self):
        self.connection.execute(
            """UPDATE characters set location_id = :location_id, name = :name, user_id = :user_id,
            weapon_id = :weapon_id, armor_id = :armor_id, experience = :experience, lvl = :lvl,
            exp_gain_time = :exp_gain_time, trait_id = :trait_id
            where character_id = :character_id""",
            {"location_id": self.location_id, "name": self.name, "user_id": self.user_id,
             "character_id": self.char_id, "weapon_id": self.weapon_id, "armor_id": self.armor_id,
             "experience": self.experience, "lvl": self.lvl, "exp_gain_time": self.exp_gain_time,
             "trait_id": self.trait_id}
        )

    def delete(self):
        for bounty in Bounty.find_all_by_character(self, self.connection):
            bounty.delete()
        self.connection.execute(
            """DELETE FROM characters WHERE character_id = ?""",
            (self.char_id,)
        )

    @classmethod
    def create(cls, name, user_id, experience, lvl, location_id, weapon_id, armor_id, exp_gain_time,
               connection):
        trait_id = random.choice(Trait.data_by_id.values()).id
        cursor = connection.execute(
            '''INSERT INTO characters (name, user_id, experience, lvl, location_id, weapon_id, armor_id, trait_id,
            exp_gain_time)
            VALUES (:name, :user_id, :experience, :lvl, :location_id, :weapon_id, :armor_id, :trait_id,
            :exp_gain_time)''',
            {"name": name, "user_id": user_id, "location_id": location_id, "lvl": lvl, "weapon_id": weapon_id,
             "armor_id": armor_id, "experience": experience, "trait_id": trait_id, "exp_gain_time": exp_gain_time}
        )
        connection.commit()
        return cls(cursor.lastrowid, name, user_id, experience, lvl, location_id, weapon_id, armor_id, trait_id,
                   exp_gain_time, connection=connection)

    @classmethod
    def find(cls, character_id, connection):
        cursor = connection.execute(
            """SELECT * from characters
            WHERE character_id = :character_id""",
            {"character_id": character_id}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def find_by_user(cls, user_id, connection):
        cursor = connection.execute(
            """SELECT * from characters
            WHERE user_id = :user_id""",
            {"user_id": user_id}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def find_by_name(cls, name, connection):
        cursor = connection.execute(
            """SELECT * from characters
            WHERE name = :name""",
            {"name": name}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def find_by_past_exp_time(cls, connection):
        cursor = connection.execute(
            """ SELECT * from characters
            WHERE exp_gain_time <= ? """,
            (dt.datetime.now(utc),)
        )
        characters = []
        for row in cursor:
            characters.append(cls(*row, connection=connection))
        return characters

    @classmethod
    def create_table_if_not_exists(cls, connection):
        """timestamp can be null, if stream goes offline for example"""
        Trait.create_table_if_not_exists(connection)
        Special.create_table_if_not_exists(connection)
        # TODO: create specials join table with user_cooldown
        connection.execute(
            """create table if not exists characters
            (character_id integer PRIMARY KEY   NOT NULL,
            name            text    UNIQUE    NOT NULL,
            user_id         text    UNIQUE    NOT NULL,
            experience      integer NOT NULL,
            lvl             integer NOT NULL,
            location_id     integer NOT NULL,
            weapon_id       integer,
            armor_id        integer,
            trait_id        text    NOT NULL,
            exp_gain_time   timestamp,
              FOREIGN KEY (location_id) REFERENCES locations(location_id),
              FOREIGN KEY (weapon_id)   REFERENCES weapons(weapon_id),
              FOREIGN KEY (armor_id)    REFERENCES armors(armor_id),
              FOREIGN KEY (trait_id)    REFERENCES traits(orig_name)
            );"""
        )

    @classmethod
    def load_static_data(cls, connection):
        Trait.load_traits(connection)


class Trait(StaticData):
    data_by_name = {}
    data_by_id = {}

    class Traits(Enum):
        DURABLE = "Durable"
        STRONG = "Strong"
        WISE = "Wise"
        GREEDY = "Greedy"
        ALERT = "Alert"
        LUCKY = "Lucky"
        VIOLENT = "Violent"
        PACIFIST = "Pacifist"

    def __init__(self, orig_name, name, connection):
        super(Trait, self).__init__(orig_name, name, connection)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists traits
                (orig_name      text  PRIMARY KEY   NOT NULL,
                name            text  UNIQUE        NOT NULL
                );""")

    @classmethod
    def create_traits(cls, script_settings, connection):
        """creates weapons into the database"""
        # TODO: button to dynamically add zones/weapons/armors
        traits = []
        # noinspection PyTypeChecker
        for trait in cls.Traits:
            if getattr(script_settings, trait.name.lower() + "_enabled"):
                traits.append((trait.value, getattr(script_settings, trait.name.lower() + "_name")))
        connection.executemany('INSERT OR IGNORE INTO traits(orig_name, name) VALUES (?, ?)', traits)
        connection.commit()

    @classmethod
    def load_traits(cls, connection):
        """loads weapons from database"""
        cursor = connection.execute('SELECT orig_name, name FROM traits')
        for row in cursor:
            trait = cls(*row, connection=connection)
            cls.data_by_id[trait.id] = trait
            cls.data_by_name[trait.name] = trait


class Special(StaticData):
    """The specials self are static, the join-table won't be"""
    data_by_name = {}
    data_by_id = {}

    def __init__(self, orig_name, name, identifier, cooldown_time, connection):
        super(Special, self).__init__(orig_name, name, connection)
        self.cooldown_time = cooldown_time
        self.identifier = identifier

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists specials
            (orig_name      text    PRIMARY KEY  NOT NULL,
            name            text    NOT NULL,
            identifier      char    UNIQUE       NOT NULL,
            cooldown_time   integer NOT NULL
            );""")

    @classmethod
    def load_specials(cls, connection):
        """loads weapons from database"""
        cursor = connection.execute('SELECT orig_name, name, identifier, cooldown_time FROM specials')
        for row in cursor:
            special = cls(*row, connection=connection)
            cls.data_by_id[special.id] = special
            cls.data_by_name[special.name] = special
