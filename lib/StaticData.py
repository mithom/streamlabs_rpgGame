import json
import codecs
import os


class StaticData(object):
    def __init__(self, connection):
        # self.connection = connection
        pass


class Map(object):
    _map = None
    y_max = 0
    x_max = 0
    _starting_position = None
    _boss_location = None

    @staticmethod
    def read_map():
        path = os.path.join(os.path.split(os.path.dirname(__file__))[0], "data\Map.json")
        with codecs.open(path, encoding="utf-8-sig", mode="r") as f:
            return json.load(f, encoding="utf-8")

    @classmethod
    def starting_position(cls):
        if cls._starting_position is None:
            cls.get_map()
        return cls._starting_position

    @classmethod
    def boss_location(cls):
        if cls._boss_location is None:
            cls.get_map()
        return cls._boss_location

    @classmethod
    def get_map(cls):
        if cls._map is None:
            map_dict = cls.read_map()
            lmap = map_dict["map"]
            cls._starting_position = map_dict["starting_coordinates"]
            cls._boss_location = map_dict["boss_coordinates"]
            cls.x_max = max([len(x) for x in lmap])
            cls.y_max = len(lmap)
            cls._map = [[Location.find_by_name(name) for name in (row + (cls.x_max - len(row)) * [None])] for row in lmap]
        return cls._map


class NamedData(StaticData):
    def __init__(self, data_id, name, connection):
        super(NamedData, self).__init__(connection)
        self.__data_id = data_id
        self.name = name

    @property
    def id(self):
        return self.__data_id

    def __eq__(self, other):
        return self.id == other.id

    @classmethod
    def find(cls, data_id):
        return cls.data_by_id.get(data_id, None)

    @classmethod
    def find_by_name(cls, name):
        return cls.data_by_name.get(name, None)


class Location(NamedData):
    data_by_name = {}
    data_by_id = {}

    def __init__(self, location_id, name, difficulty, connection):
        super(Location, self).__init__(location_id, name, connection)
        self.difficulty = difficulty

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists locations
            (location_id integer PRIMARY KEY    NOT NULL,
            name            text  UNIQUE        NOT NULL,
            difficulty      integer  NOT NULL
            );""")

    @classmethod
    def create_locations(cls, connection):
        """creates weapons into the database"""
        locations = cls.read_locations()
        connection.executemany('INSERT OR IGNORE INTO locations(name, difficulty) VALUES (?, ?)', locations)
        connection.commit()

    @staticmethod
    def read_locations():
        path = os.path.join(os.path.split(os.path.dirname(__file__))[0], "data\Locations.json")
        with codecs.open(path, encoding="utf-8-sig", mode="r") as f:
            return json.load(f, encoding="utf-8")

    @classmethod
    def load_locations(cls, connection):
        """loads weapons from database"""
        cursor = connection.execute('SELECT location_id, name, difficulty FROM locations')
        for row in cursor:
            location = cls(*row, connection=connection)
            cls.data_by_id[location.id] = location
            cls.data_by_name[location.name] = location

    @classmethod
    def update_locations(cls, connection):
        """update existing weapons with new settings"""
        pass


class Item(NamedData):

    def __init__(self, item_id, name, price, min_lvl, connection):
        super(Item, self).__init__(item_id, name, connection)
        self.price = price
        self.min_lvl = min_lvl


class Weapon(Item):
    data_by_name = {}
    data_by_id = {}

    def __init__(self, weapon_id, name, price, min_lvl, connection):
        super(Weapon, self).__init__(weapon_id, name, price, min_lvl, connection)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists weapons
                (weapon_id integer PRIMARY KEY    NOT NULL,
                name            text  UNIQUE      NOT NULL ,
                price      integer  NOT NULL,
                min_lvl     integer NOT NULL 
                );""")

    @classmethod
    def create_weapons(cls, connection):
        """creates weapons into the database"""
        weapons = cls.read_weapons()
        connection.executemany("""INSERT OR IGNORE INTO weapons(name, price, min_lvl) VALUES (?, ?, ?)""", weapons)
        connection.commit()

    @staticmethod
    def read_weapons():
        path = os.path.join(os.path.split(os.path.dirname(__file__))[0], "data\Weapons.json")
        with codecs.open(path, encoding="utf-8-sig", mode="r") as f:
            return json.load(f, encoding="utf-8")

    @classmethod
    def load_weapons(cls, connection):
        """loads weapons from database"""
        cursor = connection.execute('SELECT weapon_id, name, price, min_lvl FROM weapons')
        for row in cursor:
            weapon = cls(*row, connection=connection)
            cls.data_by_id[weapon.id] = weapon
            cls.data_by_name[weapon.name] = weapon

    @classmethod
    def update_weapons(cls):
        """update existing weapons with new settings"""
        pass


class Armor(Item):
    data_by_name = {}
    data_by_id = {}

    def __init__(self, weapon_id, name, price, min_lvl, connection):
        super(Armor, self).__init__(weapon_id, name, price, min_lvl, connection)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists armors
                (armor_id integer PRIMARY KEY   NOT NULL,
                name      text    UNIQUE        NOT NULL,
                price     integer NOT NULL,
                min_lvl   integer NOT NULL 
                );""")

    @classmethod
    def create_armors(cls, connection):
        """creates armors into the database"""
        armors = cls.read_armors()
        connection.executemany("""INSERT OR IGNORE INTO armors(name, price, min_lvl) VALUES (?, ?, ?)""", armors)
        connection.commit()

    @staticmethod
    def read_armors():
        path = os.path.join(os.path.split(os.path.dirname(__file__))[0], "data\Armors.json")
        with codecs.open(path, encoding="utf-8-sig", mode="r") as f:
            return json.load(f, encoding="utf-8")

    @classmethod
    def load_armors(cls, connection):
        """loads armors from database"""
        cursor = connection.execute('SELECT armor_id, name, price, min_lvl FROM armors')
        for row in cursor:
            armor = cls(*row, connection=connection)
            cls.data_by_id[armor.id] = armor
            cls.data_by_name[armor.name] = armor

    @classmethod
    def update_armors(cls):
        """update existing armors with new settings"""
        pass
