class Item(object):
    def __init__(self, name, price, min_lvl):
        self.name = name
        self.price = price
        self.min_lvl = min_lvl


class Weapon(Item):
    def __init__(self, name, price):
        super(Weapon, self).__init__(name, price)


class Armor(Item):
    def __init__(self, name, price):
        super(Armor, self).__init__(name, price)
