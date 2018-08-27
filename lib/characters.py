from StaticData import Weapon, Armor, NamedData
from Bounty import Bounty
import random
from enum import Enum
from pytz import utc
import datetime as dt
from Position import Position
from Attack import Attack


class Character(object):
    """
    by default lazy load static data, this is in memory anyway
    """
    game = None
    Parent = None

    def __init__(self, char_id, name, user_id, experience, lvl, weapon_id, armor_id, trait_id,
                 exp_gain_time, x, y, trait_bonus, connection, weapon=None, armor=None, trait=None):
        self.__char_id = char_id
        self.name = name
        self.user_id = user_id
        self.experience = experience
        self.lvl = lvl
        if exp_gain_time.tzinfo is None:
            exp_gain_time = utc.localize(exp_gain_time)
        self.exp_gain_time = exp_gain_time

        self.weapon_id = weapon_id
        self._weapon = weapon

        self.armor_id = armor_id
        self._armor = armor

        self.trait_id = Trait.Traits(trait_id)  # This is an enum
        self._trait = trait
        self.trait_bonus = trait_bonus

        self._specials = None

        self.position = Position(x, y)

        self.connection = connection

    @property
    def char_id(self):
        return self.__char_id

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
            self._trait = TraitStrength(self.trait_id, self.trait_bonus, self.lvl, self)
        return self._trait

    @trait.setter
    def trait(self, trait):
        self._trait = trait
        self.trait_id = trait.trait.id
        self.trait_bonus = trait.strength
        trait.character = self

    @property
    def specials(self):
        if self._specials is None:
            self._specials = SpecialCooldown.find_by_character_id(self.char_id, self.connection)
        return self._specials

    def attempt_flee(self):
        if random.random() * 100 <= 45:
            self.position.coord = random.choice(self.position.flee_options())
            self.save()
            return True
        return False

    def exp_for_difficulty(self, difficulty):
        weapon_bonus = 0
        if self.weapon is not None:
            weapon_bonus = self.weapon.min_lvl * 10
        return int(25 * (2 ** (0.7 * (difficulty - self.lvl) + 1)) * (100 + weapon_bonus) / 100.0)

    def exp_for_next_lvl(self):
        return int(100 + ((2.8 * self.lvl) ** 2))

    def gain_experience(self, xp):
        """gain experience, auto lvl-up
        :return True if lvl'ed up, False otherwise"""
        self.experience += xp * self.trait.experience_factor
        next_lvl_exp = self.exp_for_next_lvl()
        if self.experience >= next_lvl_exp:
            self.experience -= next_lvl_exp
            self.lvl_up()
            return True
        return False

    def lvl_up(self):
        self.lvl += 1
        if self.trait.trait.id == Trait.Traits.PACIFIST:
            if self.lvl % 2 == 1:
                self.trait.strength += 1

    def check_survival(self):
        rand = random.random() * 100
        armor_bonus = 0
        if self.armor is not None:
            armor_bonus = self.armor.min_lvl * 10
        if self.position.location.difficulty * 2 < self.lvl:
            return rand > 100 * self.trait.death_chance_factor * (
                    4 + 0.5 * (self.position.location.difficulty * 3 - self.lvl)) / (100 + armor_bonus)
        return rand > 100 * self.trait.death_chance_factor * (
                4 + 1.5 * (self.position.location.difficulty * 3 - self.lvl)) / (100.0 + armor_bonus)

    def attack(self, defender, sneak, defense_bonus=False, attack_bonus=False):
        roll = random.randint(1, 40)
        weapon_bonus = self.trait.attack_bonus + sneak * 2 * defender.trait.sneak_penalty_factor
        armor_bonus = defender.trait.defense_bonus
        if self.weapon is not None:
            weapon_bonus += self.weapon.min_lvl
        if defender.armor is not None:
            armor_bonus += defender.armor.min_lvl
        return roll + self.lvl * 2 + weapon_bonus + (attack_bonus * 2) > \
               defender.lvl * 2 + armor_bonus + 20 + (defense_bonus * 2)

    def add_kill(self):
        if self.trait.trait.id == Trait.Traits.PACIFIST:
            self.trait_bonus = 0
        elif self.trait.trait.id == Trait.Traits.VIOLENT:
            self.trait_bonus += 2
        pie_bounty = Bounty.find_by_character_name_from_piebank(self.name, self.connection)
        if pie_bounty is None:
            Bounty.create(self, None, 0, 1, self.connection)
        else:
            pie_bounty.kill_count += 1
            pie_bounty.save()

    def attack_boss(self, boss):
        roll = random.randint(1, 40)
        weapon_bonus = self.trait.attack_bonus
        if self.weapon is not None:
            weapon_bonus += self.weapon.min_lvl
        if roll + self.lvl * 2 + weapon_bonus > \
                boss.lvl * 2 + boss.defense_bonus + 20:
            success = boss.damage(1)
            boss.save()
            return success
        return False

    def save(self):
        self.connection.execute(
            """UPDATE characters set name = :name, user_id = :user_id,
            weapon_id = :weapon_id, armor_id = :armor_id, experience = :experience, lvl = :lvl,
            exp_gain_time = :exp_gain_time, trait_id = :trait_id, x = :x, y = :y, trait_bonus = :trait_bonus
            where character_id = :character_id""",
            {"name": self.name, "user_id": self.user_id,
             "character_id": self.char_id, "weapon_id": self.weapon_id, "armor_id": self.armor_id,
             "experience": self.experience, "lvl": self.lvl, "exp_gain_time": self.exp_gain_time,
             "trait_id": self.trait_id.value, "x": self.position.x, "y": self.position.y,
             "trait_bonus": self.trait_bonus}
        )

    def delete(self):
        attack = Attack.find_by_attacker_or_target(self, self.connection)
        if attack is not None and attack.boss_id is None:  # TODO: fix problem is person is attacked during boss battle and dies by boss.
            self.Parent.Log("rpgGame", "something is wrong in the code, char got deleted while still in a fight.")
        elif attack is not None:
            attack.delete()
        for bounty in Bounty.find_all_by_character(self, self.connection):
            bounty.delete()
        for special in self.specials:
            special.delete()
        self.connection.execute(
            """DELETE FROM characters WHERE character_id = ?""",
            (self.char_id,)
        )

    @classmethod
    def create(cls, name, user_id, experience, lvl, weapon_id, armor_id, exp_gain_time, x, y,
               connection):
        trait = random.choice(Trait.data_by_id.values())
        trait_bonus = trait.get_random_strength()
        trait_id = trait.id.value
        cursor = connection.execute(
            '''INSERT INTO characters (name, user_id, experience, lvl, weapon_id, armor_id, trait_id, exp_gain_time,
            x, y, trait_bonus)
            VALUES (:name, :user_id, :experience, :lvl, :weapon_id, :armor_id, :trait_id, :exp_gain_time, :x, :y,
             :trait_bonus)''',
            {"name": name, "user_id": user_id, "lvl": lvl, "weapon_id": weapon_id, "armor_id": armor_id,
             "experience": experience, "trait_id": trait_id, "exp_gain_time": exp_gain_time, "x": x, "y": y,
             "trait_bonus": trait_bonus}
        )
        connection.commit()
        return cls(cursor.lastrowid, name, user_id, experience, lvl, weapon_id, armor_id, trait_id,
                   exp_gain_time, x, y, trait_bonus, connection=connection)

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
        # characters = []
        # for row in cursor:
        #     characters.append(cls(*row, connection=connection))
        # return characters
        return map(lambda row: cls(*row, connection=connection), cursor)

    @classmethod
    def find_by_location(cls, x, y, connection):
        cursor = connection.execute(
            """ SELECT * from characters
            WHERE x = :x and y = :y""",
            {"x": x, "y": y}
        )
        return map(lambda row: cls(*row, connection=connection), cursor)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        """timestamp can be null, if stream goes offline for example"""
        Trait.create_table_if_not_exists(connection)
        Special.create_table_if_not_exists(connection)
        connection.execute(
            """create table if not exists characters
            (character_id integer PRIMARY KEY   NOT NULL,
            name            text    UNIQUE    NOT NULL,
            user_id         text    UNIQUE    NOT NULL,
            experience      integer NOT NULL,
            lvl             integer NOT NULL,
            weapon_id       integer,
            armor_id        integer,
            trait_id        text    NOT NULL,
            exp_gain_time   timestamp,
            x               integer NOT NULL,
            y               integer NOT NULL,
            trait_bonus     integer,
              FOREIGN KEY (weapon_id)   REFERENCES weapons(weapon_id),
              FOREIGN KEY (armor_id)    REFERENCES armors(armor_id),
              FOREIGN KEY (trait_id)    REFERENCES traits(orig_name)
            );"""
        )
        SpecialCooldown.create_table_if_not_exists(connection)

    @classmethod
    def load_static_data(cls, connection):
        Trait.load_traits(connection)
        Special.load_specials(connection)


class Trait(NamedData):
    """
    TODO: auto flee, recovery from dead
    """
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
        self._NamedData__data_id = self.Traits(orig_name)

    def get_random_strength(self):
        if self.id == self.Traits.DURABLE:
            return random.randint(1, 3)
        if self.id == self.Traits.STRONG:
            return random.randint(2, 4)
        if self.id == self.Traits.WISE:
            return 1 + random.randint(5, 15) * 0.1
        if self.id == self.Traits.GREEDY:
            return 1.5 + random.randint(0, 6) * 0.25
        if self.id == self.Traits.ALERT:
            return None
        if self.id == self.Traits.LUCKY:
            return 0.8 + random.randint(0, 3) * 0.05
        if self.id == self.Traits.VIOLENT:
            return -1
        if self.id == self.Traits.PACIFIST:
            return 0

    def defense_bonus(self, strength):
        return strength if self.id in [self.Traits.DURABLE, self.Traits.PACIFIST] else 0

    def attack_bonus(self, strength):
        return strength if self.id in (self.Traits.STRONG, self.Traits.VIOLENT) else 0

    def experience_factor(self, strength):
        return strength if self.id == self.Traits.WISE else 1

    def loot_factor(self, strength):
        return strength if self.id == self.Traits.GREEDY else 1

    def sneak_penalty_factor(self):
        return 0 if self.id == self.Traits.ALERT else 1

    def death_chance_factor(self, strength, lvl):
        if self.id == self.Traits.LUCKY:
            return strength
        elif self.id in [self.Traits.DURABLE or self.Traits.STRONG]:
            return 1 - max((8 - lvl) * 0.01, 0)
        return 1

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists traits
                (orig_name      text  PRIMARY KEY   NOT NULL,
                name            text  UNIQUE        NOT NULL
                );""")

    @classmethod
    def create_traits(cls, script_settings, connection):
        """creates weapons into the database"""
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


class TraitStrength(object):
    def __init__(self, orig_name, strength, lvl, character=None):
        self.trait = Trait.find(orig_name)
        self._strength = strength
        self.lvl = lvl
        self.character = character

    @property
    def strength(self):
        return self._strength

    @strength.setter
    def strength(self, value):
        self._strength = value
        self.character.trait_bonus = value

    @property
    def defense_bonus(self):
        return self.trait.defense_bonus(self.strength)

    @property
    def attack_bonus(self):
        return self.trait.attack_bonus(self.strength)

    @property
    def experience_factor(self):
        return self.trait.experience_factor(self.strength)

    @property
    def loot_factor(self):
        return self.trait.loot_factor(self.strength)

    @property
    def sneak_penalty_factor(self):
        return self.trait.sneak_penalty_factor()

    @property
    def death_chance_factor(self):
        return self.trait.death_chance_factor(self.strength, self.lvl)


class SpecialCooldown(object):
    def __init__(self, character_id, specials_orig_name, unavailable_until, connection, character=None, special=None):
        self.character_id = character_id
        self._character = character

        self.specials_orig_name = specials_orig_name
        self._special = special

        self.unavailable_until = unavailable_until

        self.connection = connection

    @property
    def character(self):
        if self._character is None:
            self._character = Character.find(self.character_id, self.connection)
        return self._character

    @character.setter
    def character(self, value):
        self._character = value
        self.character_id = value.char_id

    @property
    def special(self):
        if self._special is None:
            self._special = Special.find(self.specials_orig_name)
        return self._special

    @special.setter
    def special(self, value):
        self._special = value
        self.specials_orig_name = value.id

    def delete(self):
        pass  # TODO: implement

    def save(self):
        pass  # TODO: implement

    @classmethod
    def find_by_character_id(cls, character_id, connection):
        cursor = connection.execute("""SELECT * FROM character_specials
                              WHERE character_id = :character_id""",
                                    {"character_id": character_id})
        return map(lambda row: cls(*row, connection=connection), cursor)

    @classmethod
    def create(cls, character, special, connection, unavailable_until=None):
        if type(character) is Character:
            character = character.char_id
        if type(special) is Special:
            special = special.id
        connection.execute(
            '''INSERT INTO character_specials (character_id, specials_orig_name, unavailable_until)
            VALUES (:character_id, :specials_orig_name, :unavailable_until)''',
            {"character_id": character, "specials_orig_name": special, "unavailable_until": unavailable_until})
        return cls(character, special, unavailable_until, connection=connection)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists character_specials
            (character_id       text      NOT NULL,
            specials_orig_name  text      NOT NULL,
            unavailable_until  timestamp,
            FOREIGN KEY (character_id)   REFERENCES characters(character_id),
            FOREIGN KEY (specials_orig_name)   REFERENCES specials(orig_name),
            PRIMARY KEY (character_id, specials_orig_name)
        );""")


class Special(NamedData):
    """The specials self are static, the join-table won't be"""
    data_by_name = {}
    data_by_id = {}

    class Specials(Enum):
        PERSIST = "Persist"
        STUN = "Stun"
        TRACK = "Track"
        GUARDIAN = "Guardian"
        EMPOWER = "Empower"
        REPEL = "Repel"
        BLIND = "Blind"
        CURSE = "Curse"
        INVIS = "Invis"
        STEAL = "Steal"

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
    def create_specials(cls, script_settings, connection):
        """creates weapons into the database"""
        specials = []
        # noinspection PyTypeChecker
        for special in cls.Specials:
            if getattr(script_settings, special.name.lower() + "_enabled"):
                specials.append((special.value, getattr(script_settings, special.name.lower() + "_name"),
                                 getattr(script_settings, special.name.lower() + "_identifier"),
                                 getattr(script_settings, special.name.lower() + "_cd", 0)))
        connection.executemany('''INSERT OR IGNORE INTO specials(orig_name, name, identifier, cooldown_time)
                                VALUES (?, ?, ?, ?)''', specials)
        connection.commit()

    @classmethod
    def load_specials(cls, connection):
        """loads weapons from database"""
        cursor = connection.execute('SELECT orig_name, name, identifier, cooldown_time FROM specials')
        for row in cursor:
            special = cls(*row, connection=connection)
            cls.data_by_id[special.id] = special
            cls.data_by_name[special.name] = special
