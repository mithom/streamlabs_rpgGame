from StaticData import Location, Weapon, Armor
import os

# noinspection PyUnresolvedReferences
import clr

clr.AddReference("IronPython.SQLite.dll")
import sqlite3

Parent = None


class RpgGame(object):
    def __init__(self, script_settings, script_name, db_directory):
        self.scriptSettings = script_settings
        self.script_name = script_name
        self.db_directory = db_directory

        # Prepare everything
        self.prepare_database()

    def get_connection(self):
        return sqlite3.connect(os.path.join(self.db_directory, "database.db"))

    def prepare_database(self):
        conn = self.get_connection()
        try:
            # create all tables, location first, because character got foreign key to this
            Location.create_table_if_not_exists(conn)
            Character.create_table_if_not_exists(conn)
            Weapon.create_table_if_not_exists(conn)
            Armor.create_table_if_not_exists(conn)
            Location.create_locations(self.scriptSettings, conn)
        finally:
            conn.close()

    def apply_reload(self):
        pass

    def tick(self):
        if self.scriptSettings.only_active:
            result = Parent.GetActiveUsers()
        else:
            result = Parent.GetViewerList()
        conn = self.get_connection()
        try:
            for user_id in result:
                char = Character.find_by_user(user_id, conn)
                if char is None:
                    town = filter(lambda loc: loc.name == "Town", Location.load_locations(conn))[0]
                    char = Character.create("test", user_id, town.location_id)
                Parent.SendStreamMessage("%s zijn char %s met id %i zit in zone %s" %
                                         (char.user_id, char.name, char.char_id, char.location_id))
        finally:
            conn.close()


class Character(object):
    def __init__(self, char_id, name, user_id, location_id, connection):
        self.__char_id = char_id
        self.name = name
        self.user_id = user_id,
        self.location_id = location_id
        self.connection = connection;

    @property
    def char_id(self):
        return self.__char_id

    def save(self):
        cursor = self.connection.execute(
            """UPDATE characters set location_id = :location_id, name = :name, user_id = :user_id
            where char_id = :char_id""",
            location_id=self.location_id, name=self.name, user_id=self.user_id, char_id=self.char_id,
        )
        self.connection.commit()

    @classmethod
    def create(cls, name, user_id, location_id, connection):
        cursor = connection.execute('''INSERT INTO Characters (name, user_id, location_id)
                                        VALUES (:name, :user_id, :location_id)''',
                                    {"name": name, "user_id": user_id, "location_id": location_id})
        connection.commit()
        return cls(cursor.lastrowid, name, user_id, location_id, connection=connection)

    @classmethod
    def find_by_user(cls, user_id, connection):
        cursor = connection.execute(
            """SELECT character_id, name, user_id, location_id from characters
            WHERE user_id = :user_id""",
            {"user_id": user_id}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def create_table_if_not_exists(cls, connection):
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
