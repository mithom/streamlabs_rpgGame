from StaticData import Location, Weapon, Armor
import os

import clr
clr.AddReference("IronPython.SQLite.dll")
import sqlite3


class RpgGame(object):
    def __init__(self, script_settings, script_name, db_directory):
        self.scriptSettings = script_settings
        self.conn = sqlite3.connect(os.path.join(db_directory, "database.db"))
        self.script_name = script_name

        # Prepare everything
        self.prepare_database()

    def prepare_database(self):
        # Prepare characters classes
        Character.connection = self.conn
        Character.create_table_if_not_exists()

        Location.connection = self.conn
        Armor.connection = self.conn
        Weapon.connection = self.conn

    def apply_reload(self):
        pass

    def tick(self):
        pass


class Character(object):
    connection = None

    def __init__(self, char_id, name, user_id, location_id):
        self.__char_id = char_id
        self.name = name
        self.user_id = user_id,
        self.location_id = location_id

    @property
    def char_id(self):
        return self.__char_id

    def save(self):
        cursor = self.connection.execute(
            """UPDATE characters set location_id = :location_id, name = :name, user_id = :user_id
            where char_id = :char_id""",
            location_id=self.location_id, name=self.name, user_id=self.user_id, char_id=self.char_id,
        )
        cursor.commit()

    @classmethod
    def create(cls, name, user_id, location_id):
        cursor = cls.connection.execute('''INSERT INTO Characters (name, user_id, location_id)
                                        VALUES (:name, :user_id, :location_id)''',
                                        name=name, user_id=user_id, location_id=location_id)
        cursor.commit()
        return cls(cursor.lastrowid, name, user_id, location_id)

    @classmethod
    def find_by_user(cls, user_id):
        cursor = cls.connection.execute(
            """SELECT character_id, name, user_id, location_id from characters
            WHERE user_id = :user_id""",
            user_id=user_id
        )
        row = cursor.fetchone()
        return cls(*row)

    @classmethod
    def create_table_if_not_exists(connection):
        connection.execute(
            """create table if not exists characters
            (character_id integer PRIMARY KEY   NOT NULL,
            name            text  NOT NULL,
            user_id         text  UNIQUE ,
            location_id     integer NOT NULL,
              FOREIGN KEY (location_id) REFERENCES locations(location_id)
            );"""
        )


class Boss(object):
    def __init__(self):
        pass


class Roshan(Boss):
    def __init__(self):
        super(Roshan, self).__init__()
        pass


class Traits(object):
    def __init__(self):
        pass


class Specials(object):
    def __init__(self):
        pass