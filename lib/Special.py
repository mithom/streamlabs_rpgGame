import characters
from StaticData import NamedData
from enum import Enum
import datetime as dt
from pytz import utc
import random

random = random.WichmannHill()


class AutoNumber(Enum):
    def __new__(cls):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj


class SpecialCooldown(object):
    Parent = None
    format_message = None
    max_steal_amount = None

    def __init__(self, character_id, specials_orig_name, unavailable_until, connection, character=None, special=None):
        self.character_id = character_id
        self._character = character

        self.specials_orig_name = Special.Specials(specials_orig_name)
        self._special = special

        self.unavailable_until = unavailable_until

        self.connection = connection

    @property
    def character(self):
        if self._character is None:
            self._character = characters.Character.find(self.character_id, self.connection)
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

    def use(self, target):  # target is from the class character, not a string
        self.unavailable_until = dt.datetime.now(utc) + dt.timedelta(seconds=self.special.cooldown_time)
        self.save()
        if self.specials_orig_name is Special.Specials.TRACK:
            self.Parent.SendStreamMessage(self.format_message(
                "{0}, after spying on {1} you learned he is located at ({x}, {y}) where he is wearing {armor} and using"
                " {weapon}. Hes trait is {trait} and he can do {specials}.",
                self.Parent.GetDisplayName(self.character.user_id),
                target.name,
                x=target.position.x,
                y=target.position.y,
                weapon=getattr(target.weapon, "name", "hes bare hands"),
                armor=getattr(target.armor, "name", "rags"),
                trait=target.trait.trait.name,
                specials=", ".join(map(lambda x: x.special.name, target.specials)) or "nothing special"
            ))
        elif self.specials_orig_name is Special.Specials.STEAL:
            amount = int(round(random.random() * self.max_steal_amount))
            amount = min(amount, self.Parent.GetPoints(target.user_id))
            target_username = self.Parent.GetDisplayName(target.user_id)
            self.Parent.RemovePoints(target.user_id, target_username, amount)
            username = self.Parent.GetDisplayName(self.character.user_id)
            self.Parent.AddPoints(self.character.user_id, username, amount)
            self.Parent.SendStreamMessage(self.format_message(
                "{0} has stolen {amount} {currency_name} from {target_name}",
                username,
                amount=amount,
                currency_name=self.Parent.GetCurrencyName(),
                target_name=target_username
            ))
        elif self.specials_orig_name is Special.Specials.REPEL:
            for effect in ActiveEffect.find_all_by_target(target, self.connection):
                if effect.usable_orig_name is not Special.Specials.GUARDIAN:
                    effect.delete()
            ActiveEffect.create(target, self.special, self.connection)
            self.Parent.SendStreamMessage(self.format_message(
                "{0} has cleansed hes soul and is now repelling other effects for {1} seconds",
                target.name, self.special.duration
            ))
        else:
            ActiveEffect.create(target, self.special, self.connection)
            self.Parent.SendStreamMessage(self.format_message(
                "{0} has the {1} effect for {2} seconds",
                target.name, self.special.name, self.special.duration
            ))

    def delete(self):
        self.connection.execute("""DELETE FROM character_specials
                                WHERE character_id = ? and specials_orig_name = ?""",
                                (self.character_id, self.specials_orig_name.value))

    @classmethod
    def delete_all_from_character(cls, character, connection):
        if type(character) is characters.Character:
            character = character.char_id
        connection.execute("""DELETE FROM character_specials
                            WHERE character_id = ?""",
                           (character,))

    def save(self):
        self.connection.execute(
            """UPDATE character_specials set unavailable_until = :unavailable_until
            where character_id = :character_id and specials_orig_name = :orig_name""",
            {"character_id": self.character_id, "orig_name": self.specials_orig_name.value,
             "unavailable_until": self.unavailable_until}
        )

    @classmethod
    def find_by_character_id(cls, character_id, connection):
        cursor = connection.execute("""SELECT * FROM character_specials
                              WHERE character_id = :character_id""",
                                    {"character_id": character_id})
        return map(lambda row: cls(*row, connection=connection), cursor)

    @classmethod
    def create(cls, character, special, connection, unavailable_until=None):
        if type(character) is characters.Character:
            character = character.char_id
        if type(special) is Special:
            special = special.id.value
        if type(special) is Special.Specials:
            special = special.value
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
            FOREIGN KEY (specials_orig_name)   REFERENCES usable(orig_name),
            PRIMARY KEY (character_id, specials_orig_name)
        );""")


class Usable(NamedData):
    data_by_name = {}
    data_by_id = {}

    class Classes(AutoNumber):
        Special = ()
        Item = ()

    def __init__(self, orig_name, name, identifier, duration, connection):
        super(Usable, self).__init__(orig_name, name, connection)
        self.identifier = identifier
        self.duration = duration
        self.type = self.Classes[self.__class__.__name__]

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists usable
            (orig_name      text    PRIMARY KEY  NOT NULL,
            name            text    NOT NULL,
            identifier      char    UNIQUE       NOT NULL,
            duration        integer,
            class           integer NOT NULL
            );""")


class Special(Usable):
    """The specials self are static, the join-table won't be"""
    unknown = None

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
        UNKNOWN = "Unknown"  # does nothing

    def __init__(self, orig_name, name, identifier, cooldown_time, duration, connection):
        if type(orig_name) is not self.Specials:
            orig_name = self.Specials(orig_name)
        super(Special, self).__init__(orig_name, name, identifier, duration, connection)
        self.cooldown_time = cooldown_time

    @classmethod
    def available_specials(cls, character):
        specials = set(cls.data_by_id.keys())
        character_specials = set(map(lambda x: x.specials_orig_name, character.specials))
        return specials - character_specials

    # noinspection PyMethodOverriding
    @classmethod
    def find(cls, data_id):
        return super(Special, cls).find(data_id, cls.unknown)

    # noinspection PyMethodOverriding
    @classmethod
    def find_by_name(cls, name):
        return super(Special, cls).find_by_name(name, cls.unknown)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        super(Special, cls).create_table_if_not_exists(connection)
        if "cooldown_time" not in [i[1] for i in connection.execute("""PRAGMA table_info(usable)""")]:
            connection.execute("""ALTER TABLE usable ADD COLUMN cooldown_time integer;""")

    @classmethod
    def create_or_update_specials(cls, script_settings, connection):
        """creates weapons into the database and update existing ones.
        Weapons must be reloaded afterwards"""

        def should_create(special):
            return (getattr(script_settings, special.name.lower() + "_enabled") and special not in cls.data_by_id) or \
                   (special is cls.Specials.UNKNOWN and cls.unknown is None)

        cls.load_specials(script_settings, connection)
        # noinspection PyTypeChecker
        new_specials = [(new_special.value, getattr(script_settings, new_special.name.lower() + "_name"),
                         getattr(script_settings, new_special.name.lower() + "_identifier"),
                         getattr(script_settings, new_special.name.lower() + "_cd", None),
                         cls.Classes[cls.__name__].value,
                         getattr(script_settings, new_special.name.lower() + "_duration", None))
                        for new_special in cls.Specials if should_create(new_special)]
        connection.executemany('''INSERT INTO usable(orig_name, name, identifier, cooldown_time, class, duration)
                                VALUES (?, ?, ?, ?, ?, ?)''', new_specials)
        # noinspection PyUnresolvedReferences
        updated_specials = [(getattr(script_settings, updated_special.name.lower() + "_name"),
                             getattr(script_settings, updated_special.name.lower() + "_identifier"),
                             getattr(script_settings, updated_special.name.lower() + "_cd", None),
                             getattr(script_settings, updated_special.name.lower() + "_duration", None),
                             updated_special.value) for updated_special in
                            cls.data_by_id.keys() + [cls.Specials.UNKNOWN] if updated_special in cls.Specials]
        connection.executemany('''UPDATE usable SET name = ?, identifier = ?, cooldown_time = ?, duration = ?
                                WHERE orig_name = ?''', updated_specials)
        connection.commit()
        cls.reset()

    @classmethod
    def load_specials(cls, script_settings, connection):
        """loads weapons from database"""
        cursor = connection.execute('''SELECT orig_name, name, identifier, cooldown_time, duration FROM usable
                                    WHERE class = ?''', (cls.Classes[cls.__name__].value,))
        for row in cursor:
            special = cls(*row, connection=connection)
            if getattr(script_settings, special.id.name.lower() + "_enabled"):
                cls.data_by_id[special.id] = special
                cls.data_by_name[special.name] = special
            if special.id == cls.Specials.UNKNOWN:
                cls.unknown = special


class Item(Usable):
    """The items self are static, the join-table won't be"""

    class Items(Enum):
        WARP_TONIC = "WarpTonic"
        MAGICAL_ELIXIR = "MagicalElixir"  # use special only once (or perm, and potion for 1 use)
        POTION_OF_STRENGTH = "PotionOfStrength"  # temp +2 str
        BULL_ELIXIR = 'BullElixir'  # perm +1 str
        TOURNAMENT_TICKET = 'TournamentTicket'
        POTION_OF_DEFENSE = 'PotionOfDefense'  # temp +2 def
        STONE_ELIXIR = 'StoneElixir'  # perm +1 def

    def __init__(self, orig_name, name, identifier, price, duration, min_lvl, connection):
        if type(orig_name) is not self.Items:
            orig_name = self.Items(orig_name)
        super(Item, self).__init__(orig_name, name, identifier, duration, connection)
        self.price = price
        self.duration = duration  # not needed
        self.min_lvl = min_lvl

    def can_buy(self, character):
        if self.id is self.Items.MAGICAL_ELIXIR:
            return len(Special.available_specials(character)) > 0
        elif self.id is self.Items.TOURNAMENT_TICKET:
            return ActiveEffect.find_by_target_and_special(character, self.id, character.connection) is None and \
                   character.lvl >= max(characters.Character.game.scriptSettings.min_fight_lvl, 5)
        elif self.id in (
                self.Items.WARP_TONIC, self.Items.BULL_ELIXIR, self.Items.STONE_ELIXIR, self.Items.POTION_OF_DEFENSE,
                self.Items.POTION_OF_STRENGTH):
            return ActiveEffect.find_by_target_and_special(character, self.id, character.connection) is None
        else:
            raise NotImplementedError(str(self.id) + " is not implemented in can_buy")

    def use(self, character):
        if self.id is self.Items.MAGICAL_ELIXIR:
            character.gain_special()
        else:
            ActiveEffect.create(character, self, character.connection)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        super(Item, cls).create_table_if_not_exists(connection)
        if "price" not in [i[1] for i in connection.execute("""PRAGMA table_info(usable)""")]:
            connection.execute("""ALTER TABLE usable ADD COLUMN price integer;""")
            connection.execute("""ALTER TABLE usable ADD COLUMN min_lvl integer;""")

    @classmethod
    def create_or_update_items(cls, script_settings, connection):
        """creates weapons into the database and update existing ones.
        Weapons must be reloaded afterwards"""

        def should_create(item):
            return getattr(script_settings, item.name.lower() + "_enabled") and item not in cls.data_by_id

        cls.load_items(script_settings, connection)
        # noinspection PyTypeChecker
        new_items = [(new_item.value, getattr(script_settings, new_item.name.lower() + "_name"),
                      getattr(script_settings, new_item.name.lower() + "_price"),
                      getattr(script_settings, new_item.name.lower() + "_duration", None),
                      getattr(script_settings, new_item.name.lower() + "_min_lvl"),
                      getattr(script_settings, new_item.name.lower() + "_identifier"),
                      cls.Classes[cls.__name__].value)
                     for new_item in cls.Items if should_create(new_item)]
        connection.executemany('''INSERT INTO usable(orig_name, name, price, duration, min_lvl, identifier, class)
                                VALUES (?, ?, ?, ?, ?, ?, ?)''', new_items)
        # noinspection PyUnresolvedReferences
        updated_items = [(getattr(script_settings, updated_item.name.lower() + "_name"),
                          getattr(script_settings, updated_item.name.lower() + "_price"),
                          getattr(script_settings, updated_item.name.lower() + "_duration", None),
                          getattr(script_settings, updated_item.name.lower() + "_min_lvl"),
                          getattr(script_settings, updated_item.name.lower() + "_identifier"),
                          updated_item.value) for updated_item in cls.data_by_id.keys() if updated_item in cls.Items]
        connection.executemany('''UPDATE usable SET name = ?, price = ?, duration = ?, min_lvl = ?, identifier = ?
                                WHERE orig_name = ?''', updated_items)
        connection.commit()
        cls.reset()

    @classmethod
    def load_items(cls, script_settings, connection):
        """loads weapons from database"""
        cursor = connection.execute('''SELECT orig_name, name, identifier, price, duration, min_lvl FROM usable
                                    WHERE class = ?''', (cls.Classes[cls.__name__].value,))
        for row in cursor:
            item = cls(*row, connection=connection)
            if getattr(script_settings, item.id.name.lower() + "_enabled"):
                cls.data_by_id[item.id] = item
                cls.data_by_name[item.name] = item


class ActiveEffect(object):
    def __init__(self, target_id, usable_orig_name, expiration_time, connection, target=None, usable=None):
        self.connection = connection

        self.target_id = target_id
        self._target = target
        if isinstance(usable_orig_name, str) or isinstance(usable_orig_name, unicode):

            usable = Usable.find_by_name(usable_orig_name)
            self.usable_orig_name = usable.id
        else:
            self.usable_orig_name = usable_orig_name
        self._usable = usable

        self.expiration_time = expiration_time

    @property
    def target(self):
        if self._target is None:
            self._target = characters.Character.find(self.target_id, self.connection)
        return self._target

    @target.setter
    def target(self, value):
        self._target = value
        self.target_id = value.char_id

    @property
    def usable(self):
        if self._usable is None:
            self._usable = Usable.find(self.usable_orig_name)
        return self._usable

    @usable.setter
    def usable(self, value):
        self._usable = value
        self.usable_orig_name = value.id

    def delete(self):
        self.connection.execute("""DELETE FROM active_effects
                                WHERE target_id = ? and usable_orig_name = ?""",
                                (self.target_id, self.usable_orig_name.value,))

    @classmethod
    def delete_all_by_target(cls, target, connection):
        if type(target) is characters.Character:
            target = target.char_id
        connection.execute("""DELETE FROM active_effects
                            WHERE target_id = ?""",
                           (target,))

    @classmethod
    def delete_by_target_and_usable(cls, target, usable, connection):
        if isinstance(usable, Usable):
            usable = usable.id.value
        if type(usable) is Special.Specials or type(usable) is Item.Items:
            usable = usable.value
        if type(target) is characters.Character:
            target = target.char_id
        connection.execute("""DELETE FROM active_effects
                                WHERE target_id = ? AND usable_orig_name = ?""",
                           (target, usable))

    @classmethod
    def delete_all_expired(cls, connection):
        connection.execute("""DELETE FROM active_effects
                            WHERE expiration_time <= ?""",
                           (dt.datetime.now(utc),))

    @classmethod
    def find_all_by_target(cls, target, connection):
        if type(target) is characters.Character:
            target = target.char_id
        cursor = connection.execute("""SELECT * FROM active_effects
                                    WHERE target_id = :target""",
                                    {"target": target})
        return map(lambda row: cls(*row, connection=connection), cursor)

    @classmethod
    def find_by_target_and_special(cls, target, usable, connection):
        if isinstance(usable, Usable):
            usable = usable.id.value
        if type(usable) is Special.Specials or type(usable) is Item.Items:
            usable = usable.value
        if type(target) is characters.Character:
            target = target.char_id
        cursor = connection.execute("""SELECT * FROM active_effects
                                    WHERE target_id = :target AND usable_orig_name = :special""",
                                    {"target": target, "special": usable})
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def create(cls, target, usable, connection):
        if isinstance(target, characters.Character):
            target = target.char_id
        if isinstance(usable, Usable):
            usable_id = usable.id
        else:
            usable_id = usable
            usable = Usable.find(usable_id)

        expiration_time = dt.datetime.now(utc) + \
                          dt.timedelta(seconds=usable.duration) if usable.duration is not None else None
        connection.execute(
            '''INSERT INTO active_effects (target_id, usable_orig_name, expiration_time)
            VALUES (:target_id, :specials_orig_name, :expiration_time)''',
            {"target_id": target, "specials_orig_name": usable_id.value, "expiration_time": expiration_time})
        return cls(target, usable_id, expiration_time, connection=connection)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists active_effects
            (target_id            text      NOT NULL,
            usable_orig_name      text      NOT NULL,
            expiration_time       timestamp,
            FOREIGN KEY (target_id)           REFERENCES characters(character_id),
            FOREIGN KEY (usable_orig_name)    REFERENCES usable(orig_name),
            PRIMARY KEY (target_id, usable_orig_name)
            );""")
