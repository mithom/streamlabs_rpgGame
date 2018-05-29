class StaticData(object):
    data_by_name = {}
    data_by_id = {}

    def __init__(self, data_id, name, connection):
        self.connection = connection
        self.__data_id = data_id
        self.name = name

    @property
    def id(self):
        return self.__data_id

    def __eq__(self, other):
        return self.id == other.id

    @classmethod
    def find(cls, data_id):
        return cls.data_by_id[data_id]

    @classmethod
    def find_by_name(cls, name):
        return cls.data_by_name[name]


class Location(StaticData):

    def __init__(self, location_id, name, difficulty, connection):
        super(Location, self).__init__(location_id, name, connection)
        self.difficulty = difficulty

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists locations
            (location_id integer PRIMARY KEY   NOT NULL,
            name            text  UNIQUE ,
            difficulty      integer  NOT NULL
            );""")

    @classmethod
    def create_locations(cls, script_settings, connection):
        """creates weapons into the database"""
        # TODO: button to dynamically add zones/weapons/armors
        locations = [("Town", 1), ("Castle", 0), ("Forest", 3), ("Fields", 2)]
        connection.executemany('INSERT INTO locations(name, difficulty) VALUES (?, ?)', locations)
        connection.commit()

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


class Item(StaticData):

    def __init__(self, item_id, name, price, min_lvl, connection):
        super(Item, self).__init__(item_id, name, connection)
        self.price = price
        self.min_lvl = min_lvl


class Weapon(Item):
    def __init__(self, weapon_id, name, price, min_lvl, connection):
        super(Weapon, self).__init__(weapon_id, name, price, min_lvl, connection)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists weapons
                (weapon_id integer PRIMARY KEY   NOT NULL,
                name            text  UNIQUE,
                price      integer  NOT NULL,
                min_lvl     integer NOT NULL 
                );""")

    @classmethod
    def create_weapons(cls, script_settings):
        """creates weapons into the database"""
        pass

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
    def __init__(self, weapon_id, name, price, min_lvl, connection):
        super(Armor, self).__init__(weapon_id, name, price, min_lvl, connection)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists armors
                (armor_id integer PRIMARY KEY   NOT NULL,
                name            text  UNIQUE ,
                price      integer  NOT NULL,
                min_lvl     integer NOT NULL 
                );""")

    @classmethod
    def create_armors(cls, script_settings):
        """creates armors into the database"""
        pass

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
