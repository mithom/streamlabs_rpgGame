class StaticData(object):
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
        return cls.data_by_id.get(data_id, None)

    @classmethod
    def find_by_name(cls, name):
        return cls.data_by_name.get(name, None)


class Location(StaticData):
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
    def create_locations(cls, script_settings, connection):
        """creates weapons into the database"""
        # TODO: button to dynamically add zones/weapons/armors
        locations = [("Castle", 0), ("Town", 1), ("Fields", 2), ("Forest", 3), ("River", 3), ("Swamps", 4),
                     ("Mountains", 5), ("Ruins", 5), ("Dessert", 6), ("Caves", 6), ("Crypt", 8), ("Abyss", 10)]
        connection.executemany('INSERT OR IGNORE INTO locations(name, difficulty) VALUES (?, ?)', locations)
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
        weapons = [("Dagger", 5, 1), ("WoodenClub", 10, 3), ("ShortSword", 25, 6), ("Spear", 50, 9),
                   ("LongSword", 100, 12), ("SteelAxe", 250, 15), ("Katana", 400, 18), ("SpiritLance", 800, 21),
                   ("EnchantedBow", 2000, 24), ("Demon Edge", 5000, 27)]
        connection.executemany("""INSERT OR IGNORE INTO weapons(name, price, min_lvl) VALUES (?, ?, ?)""", weapons)
        connection.commit()

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
        armors = [("ClothRobe", 5, 1), ("FurArmor", 10, 2), ("LeatherArmor", 25, 4), ("CopperArmor", 50, 6),
                  ("Chainmail", 100, 8), ("Platemail", 250, 10), ("SilverPlatemail", 400, 12),
                  ("AssaultCuirase", 800, 14), ("DragonScalemail", 2000, 16), ("Divine Aura", 5000, 18)]
        connection.executemany("""INSERT OR IGNORE INTO armors(name, price, min_lvl) VALUES (?, ?, ?)""", armors)
        connection.commit()

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
