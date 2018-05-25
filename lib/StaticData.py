class Location(object):
    connection = None

    def __init__(self):
        pass

    @classmethod
    def create_locations(cls, script_settings):
        """creates weapons into the database"""
        pass

    @classmethod
    def load_locations(cls):
        """loads weapons from database"""
        pass

    @classmethod
    def update_locations(cls):
        """update existing weapons with new settings"""
        pass


class Item(object):
    connection = None

    def __init__(self, name, price, min_lvl):
        self.name = name
        self.price = price
        self.min_lvl = min_lvl


class Weapon(Item):
    def __init__(self, name, price, min_lvl):
        super(Weapon, self).__init__(name, price, min_lvl)

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
