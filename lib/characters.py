from StaticData import Weapon, Armor, NamedData
from Bounty import Bounty
import random
from enum import Enum
from pytz import utc
import datetime as dt
from Position import Position
from Attack import Attack
from Special import SpecialCooldown, Special, ActiveEffect, Item
import King

random = random.WichmannHill()


class Character(object):
    """
    by default lazy load static data, this is in memory anyway
    """
    game = None
    Parent = None
    format_message = None
    cache = {}

    def __init__(self, char_id, name, user_id, experience, lvl, weapon_id, armor_id, trait_id,
                 exp_gain_time, x, y, trait_bonus, alive, connection, weapon=None, armor=None, trait=None):
        self.__char_id = char_id

        self.cache[self.__char_id] = self

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
        self.alive = alive

        self.connection = connection

    def __eq__(self, other):
        if type(other) is int:
            return self.char_id == other
        if type(other) is not self.__class__:
            return False
        return self.char_id == other.char_id

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
        if weapon is not None:
            self.weapon_id = weapon.id
        else:
            self.weapon_id = None

    @property
    def armor(self):
        if self._armor is None and self.armor_id is not None:
            self._armor = Armor.find(self.armor_id)
        return self._armor

    @armor.setter
    def armor(self, armor):
        self._armor = armor
        if armor is not None:
            self.armor_id = armor.id
        else:
            self.armor_id = None

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

    @property
    def armor_bonus(self):
        armor_bonus = self.trait.defense_bonus
        if self.armor is not None:
            armor_bonus += self.armor.min_lvl
        if ActiveEffect.find_by_target_and_special(self, Item.Items.POTION_OF_DEFENSE, self.connection):
            armor_bonus += 4
        if ActiveEffect.find_by_target_and_special(self, Item.Items.STONE_ELIXIR, self.connection):
            armor_bonus += 2
        return armor_bonus

    @property
    def attack_bonus(self):
        attack_bonus = self.trait.attack_bonus
        if self.weapon is not None:
            attack_bonus += self.weapon.min_lvl
        if ActiveEffect.find_by_target_and_special(self, Special.Specials.EMPOWER, self.connection):
            attack_bonus += 4
        if ActiveEffect.find_by_target_and_special(self, Item.Items.POTION_OF_STRENGTH, self.connection):
            attack_bonus += 4
        if ActiveEffect.find_by_target_and_special(self, Item.Items.BULL_ELIXIR, self.connection):
            attack_bonus += 2
        return attack_bonus

    def is_stunned(self):
        return ActiveEffect.find_by_target_and_special(self, Special.Specials.STUN, self.connection) is not None

    def is_invisible(self):
        return ActiveEffect.find_by_target_and_special(self, Special.Specials.INVIS, self.connection) is not None

    def remove_invisibility(self):
        invisibility = ActiveEffect.find_by_target_and_special(self, Special.Specials.INVIS, self.connection)
        if invisibility is not None:
            invisibility.delete()

    def attempt_flee(self, vs_lvl):
        if random.random() * 100 <= (45 - self.lvl + vs_lvl + self.trait.flee_bonus):
            self.position.coord = random.choice(self.position.flee_options())
            self.save()
            return True
        return False

    def loot(self, target):
        if target.trait_id == Trait.Traits.ALERT:
            return 0
        loot_amount = min(random.randint(1, self.game.scriptSettings.max_steal_amount),
                          self.Parent.GetPoints(target.user_id))
        if self.Parent.RemovePoints(target.user_id, self.Parent.GetDisplayName(self.user_id), loot_amount):
            self.Parent.AddPoints(self.user_id, self.Parent.GetDisplayName(self.user_id), loot_amount)
            return loot_amount
        return 0

    def exp_for_difficulty(self, difficulty):
        weapon_bonus = 0
        if self.weapon is not None:
            weapon_bonus = self.weapon.min_lvl * 10
        return round(
            (max(7 + (self.lvl - 1) / 2 + 3 * (difficulty - self.lvl / 2.0), 0) ** 1.2) * (100 + weapon_bonus) / 100.0)

    def exp_for_next_lvl(self):
        return round(50 + ((7 * (self.lvl - 1)) ** 1.4))

    def gain_experience(self, xp):
        """gain experience, auto lvl-up
        :return True if lvl'ed up, False otherwise"""
        self.experience += round(xp * self.trait.experience_factor)
        next_lvl_exp = self.exp_for_next_lvl()
        lvl_up = False
        while self.experience >= next_lvl_exp:
            self.experience -= next_lvl_exp
            self.lvl_up()
            next_lvl_exp = self.exp_for_next_lvl()
            lvl_up = True
        return lvl_up

    def lvl_up(self):
        self.lvl += 1
        if self.trait.trait.id == Trait.Traits.PACIFIST:
            if self.lvl % 2 == 1:
                self.trait.strength += 1
        if self.lvl == 15:
            self.gain_special()

    def gain_special(self):  # TODO: possibility to only gain selection of specials from a specific boss
        new_specials = Special.available_specials(self)
        if len(new_specials) > 0:
            new_special_id = random.choice(list(new_specials))
            special = SpecialCooldown.create(self.char_id, new_special_id, self.connection)
            self.Parent.SendStreamMessage(self.format_message(
                "{0}, {1} has gained the ability {2} ({3}) on a {4} seconds cooldown.",
                self.Parent.GetDisplayName(self.user_id),
                self.name,
                special.special.name,
                special.special.identifier,
                special.special.cooldown_time
            ))
        else:
            self.Parent.SendStreamMessage(self.format_message(
                "{0}, your character {1} already has every available special and cannot get a new one.",
                self.Parent.GetDisplayName(self.user_id),
                self.name
            ))

    def check_survival(self):
        rand = random.random() * 100
        terrain_factor = 1.5
        if self.position.location.difficulty * 2 < self.lvl:
            terrain_factor = 0.5
        death_chance = 100 * (max(2.5 + terrain_factor * (self.position.location.difficulty * 2 - self.lvl), 1)) / (
                100 + self.armor_bonus * 20)
        if ActiveEffect.find_by_target_and_special(self, Special.Specials.CURSE, self.connection):
            death_chance += 5
        if ActiveEffect.find_by_target_and_special(self, Special.Specials.GUARDIAN, self.connection):
            death_chance -= 10
        if self.lvl <= 4:
            death_chance -= 5 - self.lvl
        return rand > (self.trait.death_chance_factor * death_chance)

    def attack(self, defender, sneak, defense_bonus=False, attack_bonus=False):
        roll = random.randint(1, 40)
        weapon_bonus = self.attack_bonus + sneak * 2 * defender.trait.sneak_penalty_factor
        armor_bonus = defender.armor_bonus
        if ActiveEffect.find_by_target_and_special(self, Special.Specials.BLIND, self.connection) is not None:
            if random.random > 0.6:
                return False
        return roll + self.lvl * 2 + weapon_bonus + (attack_bonus * 2) > \
               defender.lvl * 2 + armor_bonus + 18 + (defense_bonus * 2)

    def add_kill(self):
        if self.trait.trait.id == Trait.Traits.PACIFIST:
            self.trait_bonus = 0
        elif self.trait.trait.id == Trait.Traits.VIOLENT:
            self.trait_bonus += 3
        pie_bounty = Bounty.find_by_character_name_from_piebank(self.name, self.connection)
        if pie_bounty is None:
            Bounty.create(self, None, 0, 1, self.connection)
        else:
            pie_bounty.kill_count += 1
            pie_bounty.save()
            if pie_bounty.reward > 500:
                self.Parent.SendStreamMessage(self.format_message(
                    "{0}s killing spree bounty has been increased to a dangling amount of {1} {2}",
                    self.name, pie_bounty.reward, self.Parent.GetCurrencyName()
                ))

    def attack_boss(self, boss):
        roll = random.randint(1, 40)
        weapon_bonus = self.attack_bonus
        if ActiveEffect.find_by_target_and_special(self, Special.Specials.BLIND, self.connection) is not None:
            if random.random > 0.6:
                return False
        if roll + self.lvl * 2 + weapon_bonus > \
                boss.lvl * 2 + boss.defense_bonus + 20:
            success = boss.damage(1)
            boss.save()
            self.Parent.SendStreamMessage(self.format_message(
                "{0} managed to hit the {1}, {2}/{3} HP remaining",
                self.name, boss.name, boss.hp, boss.max_hp
            ))
            return success
        self.Parent.SendStreamMessage(self.format_message(
            "{0} failed to hit boss {1}.",
            self.name, boss.name
        ))
        return False

    def use_special(self, special_enum, target):
        special_list = filter(lambda x: x.specials_orig_name == special_enum, self.specials)
        if len(special_list) > 0:
            special = special_list[0]
            if special.unavailable_until is None or special.unavailable_until < dt.datetime.now(utc):
                special.use(target)
            else:
                self.Parent.SendStreamMessage(self.format_message(
                    "{0}, you can not use that special right now, cooldown: {1}",
                    self.Parent.GetDisplayName(self.user_id),
                    str(special.unavailable_until - dt.datetime.now(utc))
                ))
        else:
            self.Parent.SendStreamMessage(self.format_message(
                "{0}, your character {1} doesn't have that special",
                self.Parent.GetDisplayName(self.user_id),
                self.name
            ))
            return

    def get_tournament(self):
        return King.Participant.find(self.char_id, self.connection)

    def participate_in_same_tournament(self, char2):
        part1 = King.Participant.find(self.char_id, self.connection)
        part2 = King.Participant.find(char2.char_id, self.connection)
        # checks tournament equality in None safe way, srry for bad == use
        return part1 == part2 and (part1 is None or (part1.alive and part2.alive))

    def die(self):
        if self.trait_id == Trait.Traits.LUCKY:
            # 15-60% chance to revive for first time, -15% each time thereafter
            if random.random() <= (1 - self.trait_bonus) * 3:
                self.trait_bonus = min(1, self.trait_bonus + 0.05)
                self.Parent.SendStreamMessage(self.format_message(
                    "{0} feels lucky today and can't shake the feeling that he should've died",
                    self.name
                ))
                self.save()
                return False
        self.alive = False
        del self.cache[self.char_id]
        self.connection.execute("""UPDATE characters set alive = 0 WHERE character_id = :char_id""",
                                {"char_id": self.char_id})
        return True

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
        if attack is not None and attack.boss_id is None:
            # TODO: fix problem when person is attacked during boss battle and dies by boss.
            self.Parent.Log("rpgGame", "something is wrong in the code, char got deleted while still in a fight.")
        elif attack is not None:
            attack.delete()
        for bounty in Bounty.find_all_by_character(self, self.connection):
            bounty.delete()
        SpecialCooldown.delete_all_from_character(self, self.connection)
        ActiveEffect.delete_all_by_target(self, self.connection)
        participant = King.Participant.find(self.char_id, self.connection)
        if participant is not None:
            participant.delete()
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
                   exp_gain_time, x, y, trait_bonus, True, connection=connection)

    @classmethod
    def find(cls, character_id, connection):
        if character_id in cls.cache:
            return cls.cache[character_id]
        cursor = connection.execute(
            """SELECT * from characters
            WHERE character_id = :character_id AND alive = 1""",
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
            WHERE user_id = :user_id AND alive = 1""",
            {"user_id": user_id}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def find_by_dead_and_user(cls, user_id, conn):
        cursor = conn.execute(
            """SELECT * from characters
            WHERE user_id = :user_id AND alive = 0""",
            {"user_id": user_id}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=conn)

    @classmethod
    def find_by_name(cls, name, connection):
        cursor = connection.execute(
            """SELECT * from characters
            WHERE name = :name AND alive = 1""",
            {"name": name}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def find_by_dead_and_name(cls, name, conn):
        cursor = conn.execute(
            """SELECT * from characters
            WHERE name = :name AND alive = 0""",
            {"name": name}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=conn)

    @classmethod
    def find_by_past_exp_time(cls, connection):
        cursor = connection.execute(
            """ SELECT * from characters
            WHERE exp_gain_time <= ? AND alive = 1""",
            (dt.datetime.now(utc),)
        )
        return map(lambda row: cls(*row, connection=connection), cursor)

    @classmethod
    def find_by_location(cls, x, y, connection):
        cursor = connection.execute(
            """ SELECT * from characters
            WHERE x = :x and y = :y AND alive = 1""",
            {"x": x, "y": y}
        )
        return map(lambda row: cls(*row, connection=connection), cursor)

    @classmethod
    def get_order_by_lvl_and_xp(cls, limit, connection, min_lvl=0, offset=0):
        cursor = connection.execute("""SELECT * FROM characters c
            WHERE c.lvl >= ? AND c.alive = 1
            ORDER BY c.lvl DESC, c.experience DESC
            LIMIT ? OFFSET ?""", (min_lvl, limit, offset))
        return map(lambda row: cls(*row, connection=connection), cursor)

    @classmethod
    def get_with_ticket_ordered_by_lvl_and_xp(cls, limit, conn, min_lvl=0, offset=0):
        cursor = conn.execute(
            """SELECT c.* FROM (
                SELECT c.*
                FROM characters c
                WHERE c.lvl >= :min_lvl AND c.alive = 1
                ORDER BY c.lvl DESC, c.experience DESC
                LIMIT -1 OFFSET :offset_
              ) AS c INNER JOIN active_effects ae on c.character_id = ae.target_id
            WHERE ae.usable_orig_name = :TT
            ORDER BY c.lvl DESC, c.experience DESC LIMIT :limit_ """,
            {"min_lvl": min_lvl, "offset_": offset, "TT": Item.Items.TOURNAMENT_TICKET.value, "limit_": limit}
        )
        return map(lambda row: cls(*row, connection=conn), cursor)

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
            trait_bonus     real,
            alive           boolean NOT NULL DEFAULT 1,
              FOREIGN KEY (weapon_id)   REFERENCES weapons(weapon_id),
              FOREIGN KEY (armor_id)    REFERENCES armors(armor_id),
              FOREIGN KEY (trait_id)    REFERENCES traits(orig_name)
            );"""
        )
        if "alive" not in [i[1] for i in connection.execute("""PRAGMA table_info(characters)""")]:
            connection.execute("""ALTER TABLE characters ADD COLUMN alive boolean NOT NULL DEFAULT 1;""")
        SpecialCooldown.create_table_if_not_exists(connection)
        ActiveEffect.create_table_if_not_exists(connection)

    @classmethod
    def load_static_data(cls, script_settings, connection):
        Trait.load_traits(script_settings, connection)
        Special.load_specials(script_settings, connection)

    @classmethod
    def reload_static_data(cls, script_settings, conn):
        Trait.create_or_update_traits(script_settings, conn)
        Special.create_or_update_specials(script_settings, conn)
        cls.load_static_data(script_settings, conn)


class Trait(NamedData):
    data_by_name = {}
    data_by_id = {}
    plain = None

    class Traits(Enum):
        DURABLE = "Durable"
        STRONG = "Strong"
        WISE = "Wise"
        GREEDY = "Greedy"
        ALERT = "Alert"
        LUCKY = "Lucky"
        VIOLENT = "Violent"
        PACIFIST = "Pacifist"
        PLAIN = "Plain"

    def __init__(self, orig_name, name, connection):
        if type(orig_name) is not self.Traits:
            orig_name = self.Traits(orig_name)
        super(Trait, self).__init__(orig_name, name, connection)

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
            return 5 + random.randint(0, 5)
        if self.id == self.Traits.LUCKY:
            return 0.8 + random.randint(0, 3) * 0.05
        if self.id == self.Traits.VIOLENT:
            return -1
        if self.id == self.Traits.PACIFIST:
            return 0
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
        return 0 if self.id == self.Traits.ALERT else 2

    def flee_bonus(self, strength):
        return strength if self.id == self.Traits.ALERT else 0

    def death_chance_factor(self, strength, lvl):
        if self.id == self.Traits.LUCKY:
            return strength
        elif self.id in [self.Traits.DURABLE or self.Traits.STRONG]:
            return 1 - max((8 - lvl) * 0.01, 0)
        return 1

    # noinspection PyMethodOverriding
    @classmethod
    def find(cls, data_id):
        return super(Trait, cls).find(data_id, cls.plain)

    # noinspection PyMethodOverriding
    @classmethod
    def find_by_name(cls, name):
        return super(Trait, cls).find_by_name(name, cls.plain)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists traits
                (orig_name      text  PRIMARY KEY   NOT NULL,
                name            text  UNIQUE        NOT NULL
                );""")

    @classmethod
    def create_or_update_traits(cls, script_settings, connection):
        """creates weapons into the database and update existing ones.
        afterwards traits need to be loaded in again"""

        def should_create(trait_sc):
            return (getattr(script_settings, trait_sc.name.lower() + "_enabled") and trait_sc not in cls.data_by_id) \
                   or (trait_sc is cls.Traits.PLAIN and cls.plain is None)

        cls.load_traits(script_settings, connection)
        # noinspection PyTypeChecker
        new_traits = [(trait.value, getattr(script_settings, trait.name.lower() + "_name")) for trait in cls.Traits if
                      should_create(trait)]
        connection.executemany('INSERT INTO traits(orig_name, name) VALUES (?, ?)', new_traits)
        # noinspection PyUnresolvedReferences
        updated_traits = [(getattr(script_settings, trait.name.lower() + "_name"), trait.value) for trait in
                          cls.data_by_id.keys() + [cls.Traits.PLAIN]]
        connection.executemany('UPDATE traits SET name = ? WHERE orig_name = ?', updated_traits)
        connection.commit()
        cls.reset()

    @classmethod
    def load_traits(cls, script_settings, connection):
        """loads weapons from database"""
        cursor = connection.execute('SELECT orig_name, name FROM traits')
        for row in cursor:
            trait = cls(*row, connection=connection)
            if getattr(script_settings, trait.id.name.lower() + "_enabled"):
                cls.data_by_id[trait.id] = trait
                cls.data_by_name[trait.name] = trait
            if trait.id == cls.Traits.PLAIN:
                cls.plain = trait


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
    def flee_bonus(self):
        return self.trait.flee_bonus(self.strength)

    @property
    def death_chance_factor(self):
        return self.trait.death_chance_factor(self.strength, self.lvl)
