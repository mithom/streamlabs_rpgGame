from StaticData import Location, Weapon, Armor, StaticData


class Character(object):
    """
    by default lazy loads the location
    TODO: add eager load option, joins on database.
    """

    def __init__(self, char_id, name, user_id, experience, lvl, location_id, weapon_id, armor_id, connection,
                 location=None, weapon=None, armor=None):
        self.__char_id = char_id
        self.name = name
        self.user_id = user_id,
        self.experience = experience
        self.lvl = lvl

        self.location_id = location_id
        self._location = location

        self.weapon_id = weapon_id
        self._weapon = weapon

        self.armor_id = armor_id
        self._armor = armor

        self.connection = connection

    @property
    def char_id(self):
        return self.__char_id

    @property
    def location(self):
        if self._location is None:
            self._location = Location.find(self.location_id)
        return self._location

    @location.setter
    def location(self, location):
        self._location = location
        self.location_id = location.id

    @property
    def weapon(self):
        if self._weapon is None:
            self._weapon = Weapon.find(self.weapon_id)
        return self._weapon

    @location.setter
    def location(self, weapon):
        self._weapon = weapon
        self.weapon_id = weapon.id

    @property
    def armor(self):
        if self._armor is None:
            self._armor = Armor.find(self.armor_id)
        return self._armor

    @location.setter
    def location(self, armor):
        self._armor = armor
        self.armor_id = armor.id

    def save(self):
        self.connection.execute(
            """UPDATE characters set location_id = :location_id, name = :name, user_id = :user_id,
            weapon_id = :weapon_id, armor_id = :armor_id, experience = :experience, lvl = :lvl
            where char_id = :char_id""",
            {"location_id": self.location_id, "name": self.name, "user_id": self.user_id, "char_id": self.char_id,
             "weapon_id": self.weapon_id, "armor_id": self.armor_id, "experience": self.experience,
             "lvl": self.lvl}
        )
        self.connection.commit()

    @classmethod
    def create(cls, name, user_id, experience, lvl, location_id, weapon_id, armor_id, connection):
        cursor = connection.execute('''INSERT INTO Characters (name, user_id, location_id, weapon_id, armor_id)
                                        VALUES (:name, :user_id, :location_id, :weapon_id, :armor_id)''',
                                    {"name": name, "user_id": user_id, "location_id": location_id, "lvl": lvl,
                                     "weapon_id": weapon_id, "armor_id": armor_id, "experience": experience, })
        connection.commit()
        return cls(cursor.lastrowid, name, experience, lvl, user_id, location_id, weapon_id, armor_id,
                   connection=connection)

    @classmethod
    def find_by_user(cls, user_id, connection):
        cursor = connection.execute(
            """SELECT character_id, name, user_id, experience, lvl, location_id, weapon_id, armor_id from characters
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
            experience      integer NOT NULL,
            lvl             integer NOT NULL,
            location_id     integer NOT NULL,
            weapon_id       integer NOT NULL,
            armor_id        integer NOT NULL,
              FOREIGN KEY (location_id) REFERENCES locations(location_id),
              FOREIGN KEY (weapon_id) REFERENCES weapons(weapon_id),
              FOREIGN KEY (armor_id) REFERENCES armors(armor_id),
            );"""
        )


class Boss(object):
    def __init__(self):
        pass


class Roshan(Boss):
    def __init__(self):
        super(Roshan, self).__init__()
        pass


class Traits(StaticData):
    def __init__(self, trait_id, name, connection):
        super(Traits, self).__init__(trait_id, connection)
        self.name = name


class Specials(object):
    """This is no static data as it needs to remember a cooldown for each user"""
    def __init__(self):
        pass
