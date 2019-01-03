import characters
from StaticData import NamedData
from enum import Enum
import datetime as dt
from pytz import utc
import random

random = random.WichmannHill()


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
                "{0}, after spying on {1} you learned he is wearing {armor} and using {weapon}. Hes trait is {trait} " +
                "and he can do {specials}.",
                self.Parent.GetDisplayName(self.character.user_id),
                target.name,
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
                if effect.specials_orig_name is not Special.Specials.GUARDIAN:
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
            FOREIGN KEY (specials_orig_name)   REFERENCES specials(orig_name),
            PRIMARY KEY (character_id, specials_orig_name)
        );""")


class Special(NamedData):
    """The specials self are static, the join-table won't be"""
    data_by_name = {}
    data_by_id = {}
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
        super(Special, self).__init__(orig_name, name, connection)
        self.cooldown_time = cooldown_time
        self.identifier = identifier
        self.duration = duration

    @classmethod
    def find(cls, data_id):
        return super(Special, cls).find(data_id, cls.unknown)

    @classmethod
    def find_by_name(cls, name):
        return super(Special, cls).find_by_name(name, cls.unknown)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists specials
            (orig_name      text    PRIMARY KEY  NOT NULL,
            name            text    NOT NULL,
            identifier      char    UNIQUE       NOT NULL,
            cooldown_time   integer,
            duration        integer
            );""")

    @classmethod
    def create_or_update_specials(cls, script_settings, connection):
        """creates weapons into the database and update existing ones.
        Weapons must be reloaded afterwards"""

        def should_create(special):
            return (getattr(script_settings, special.name.lower() + "_enabled") and special not in cls.data_by_id) or \
                   (special is cls.Specials.UNKNOWN and cls.unknown is None)

        cls.load_specials(script_settings, connection)
        # noinspection PyTypeChecker
        new_specials = [(special.value, getattr(script_settings, special.name.lower() + "_name"),
                         getattr(script_settings, special.name.lower() + "_identifier"),
                         getattr(script_settings, special.name.lower() + "_cd", None),
                         getattr(script_settings, special.name.lower() + "_duration", None))
                        for special in cls.Specials if should_create(special)]
        connection.executemany('''INSERT INTO specials(orig_name, name, identifier, cooldown_time, duration)
                                VALUES (?, ?, ?, ?, ?)''', new_specials)
        # noinspection PyUnresolvedReferences
        updated_specials = [(getattr(script_settings, special.name.lower() + "_name"),
                             getattr(script_settings, special.name.lower() + "_identifier"),
                             getattr(script_settings, special.name.lower() + "_cd", None),
                             getattr(script_settings, special.name.lower() + "_duration", None),
                             special.value) for special in cls.data_by_id.keys()+[cls.Specials.UNKNOWN]]
        connection.executemany('''UPDATE specials SET name = ?, identifier = ?, cooldown_time = ?, duration = ?
                                WHERE orig_name = ?''', updated_specials)
        connection.commit()
        cls.reset()

    @classmethod
    def load_specials(cls, script_settings, connection):
        """loads weapons from database"""
        cursor = connection.execute('SELECT orig_name, name, identifier, cooldown_time, duration FROM specials')
        for row in cursor:
            special = cls(*row, connection=connection)
            if getattr(script_settings, special.id.name.lower() + "_enabled"):
                cls.data_by_id[special.id] = special
                cls.data_by_name[special.name] = special
            if special.id == cls.Specials.UNKNOWN:
                cls.unknown = special


class ActiveEffect(object):
    def __init__(self, target_id, specials_orig_name, expiration_time, connection, target=None, special=None):
        self.connection = connection

        self.target_id = target_id
        self._target = target

        self.specials_orig_name = specials_orig_name
        self._special = special

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
    def special(self):
        if self._special is None:
            self._special = Special.find(self.specials_orig_name)
        return self._special

    @special.setter
    def special(self, value):
        self._special = value
        self.specials_orig_name = value.id

    def delete(self):
        self.connection.execute("""DELETE FROM active_effects
                                WHERE target_id = ? and specials_orig_name = ?""",
                                (self.target_id, self.specials_orig_name,))

    @classmethod
    def delete_all_by_target(cls, target, connection):
        if type(target) is characters.Character:
            target = target.char_id
        connection.execute("""DELETE FROM active_effects
                            WHERE target_id = ?""",
                           (target,))

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
    def find_by_target_and_special(cls, target, special, connection):
        if type(special) is Special:
            special = special.id.value
        if type(special) is Special.Specials:
            special = special.value
        if type(target) is characters.Character:
            target = target.char_id
        cursor = connection.execute("""SELECT * FROM active_effects
                                    WHERE target_id = :target AND specials_orig_name = :special""",
                                    {"target": target, "special": special})
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def create(cls, target, special, connection):
        if type(target) is characters.Character:
            target = target.char_id
        if type(special) is Special:
            special_id = special.id
        else:
            special_id = special
            special = Special.find(special_id)
        expiration_time = dt.datetime.now(utc) + dt.timedelta(seconds=special.duration)
        connection.execute(
            '''INSERT INTO active_effects (target_id, specials_orig_name, expiration_time)
            VALUES (:target_id, :specials_orig_name, :expiration_time)''',
            {"target_id": target, "specials_orig_name": special_id.value, "expiration_time": expiration_time})
        return cls(target, special, expiration_time, connection=connection)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists active_effects
            (target_id            text      NOT NULL,
            specials_orig_name    text      NOT NULL,
            expiration_time       timestamp NOT NULL,
            FOREIGN KEY (target_id)   REFERENCES characters(character_id),
            FOREIGN KEY (specials_orig_name)   REFERENCES specials(orig_name),
            PRIMARY KEY (target_id, specials_orig_name)
            );""")
