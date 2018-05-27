class Location(object):
    connection = None
    locations_by_id = {}
    locations_by_name = {}

    def __init__(self, location_id, name, difficulty, connection):
        self.__location_id = location_id
        self.name = name
        self.difficulty = difficulty
        self.connection = connection

    @property
    def id(self):
        return self.__location_id

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
    def find(cls, location_id):
        return cls.locations_by_id[location_id]

    @classmethod
    def find_by_name(cls, name):
        return cls.locations_by_name[name]

    @classmethod
    def load_locations(cls, connection):
        """loads weapons from database"""
        cursor = connection.execute('SELECT location_id, name, difficulty FROM locations')
        for row in cursor:
            location = cls(*row, connection=connection)
            cls.locations_by_id[location.location_id] = location
            cls.locations_by_name[location.name] = location

    @classmethod
    def update_locations(cls, connection):
        """update existing weapons with new settings"""
        pass


class Item(object):
    item_by_name = {}
    item_by_id = {}

    def __init__(self, item_id, name, price, min_lvl, connection):
        self.__item_id = item_id
        self.name = name
        self.price = price
        self.min_lvl = min_lvl
        self.connection = connection

    @property
    def id(self):
        return self.__item_id

    @classmethod
    def find(cls, item_id):
        return cls.item_by_id[item_id]

    @classmethod
    def find_by_name(cls, name):
        return cls.item_by_name[name]


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
            cls.item_by_id[weapon.id] = weapon
            cls.item_by_name[weapon.name] = weapon

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
            cls.item_by_id[armor.id] = armor
            cls.item_by_name[armor.name] = armor

    @classmethod
    def update_armors(cls):
        """update existing armors with new settings"""
        pass
