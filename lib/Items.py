class Item(object):
    def __init__(self, name, price, min_lvl):
        self.name = name
        self.price = price
        self.min_lvl = min_lvl


class Weapon(Item):
    def __init__(self, name, price, min_lvl):
        super(Weapon, self).__init__(name, price, min_lvl)


class Armor(Item):
    def __init__(self, name, price, min_lvl):
        super(Armor, self).__init__(name, price, min_lvl)


def create_weapons(script_settings):
    """creates weapons into the database"""
    pass


def load_weapons():
    """loads weapons from database"""
    pass


def update_weapons():
    """update existing weapons with new settings"""
    pass


def create_armors(script_settings):
    """creates armors into the database"""
    pass


def load_armors():
    """loads armors from database"""
    pass


def update_armors():
    """update existing armors with new settings"""
    pass
