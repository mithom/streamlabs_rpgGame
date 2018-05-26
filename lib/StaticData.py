class Location(object):
    connection = None

    def __init__(self, location_id, name, difficulty, connection):
        self.__location_id = location_id
        self.name = name
        self.difficulty = difficulty
        self.connection = connection

    @property
    def location_id(self):
        return self.__location_id

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists locations
            (location_id integer PRIMARY KEY   NOT NULL,
            name            text  NOT NULL,
            difficulty      integer  NOT NULL
            );""")

    @classmethod
    def create_locations(cls, script_settings, connection):
        """creates weapons into the database"""
        locations = [("Town", 1), ("Castle", 0), ("Forest", 3), ("Fields", 2)]
        cursor = connection.executemany('INSERT INTO locations VALUES (?, ?)', locations)
        cursor.commit()

    @classmethod
    def load_locations(cls, connection):
        """loads weapons from database"""
        cursor = connection.execute('SELECT location_id, name, difficulty FROM locations')
        return [cls(*row, connection=connection) for row in cursor]

    @classmethod
    def update_locations(cls, connection):
        """update existing weapons with new settings"""
        pass


class Item(object):
    def __init__(self, name, price, min_lvl):
        self.name = name
        self.price = price
        self.min_lvl = min_lvl


class Weapon(Item):
    def __init__(self, name, price, min_lvl):
        super(Weapon, self).__init__(name, price, min_lvl)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists weapons
                (weapon_id integer PRIMARY KEY   NOT NULL,
                name            text  NOT NULL,
                price      integer  NOT NULL,
                min_lvl     integer NOT NULL 
                );""")

    @classmethod
    def create_weapons(cls, script_settings):
        """creates weapons into the database"""
        pass

    @classmethod
    def load_weapons(cls):
        """loads weapons from database"""
        pass

    @classmethod
    def update_weapons(cls):
        """update existing weapons with new settings"""
        pass


class Armor(Item):
    def __init__(self, name, price, min_lvl):
        super(Armor, self).__init__(name, price, min_lvl)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists armors
                (weapon_id integer PRIMARY KEY   NOT NULL,
                name            text  NOT NULL,
                price      integer  NOT NULL,
                min_lvl     integer NOT NULL 
                );""")

    @classmethod
    def create_armors(cls, script_settings):
        """creates armors into the database"""
        pass

    @classmethod
    def load_armors(cls):
        """loads armors from database"""
        pass

    @classmethod
    def update_armors(cls):
        """update existing armors with new settings"""
        pass
