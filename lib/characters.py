from StaticData import Location, Weapon, Armor, StaticData


class Character(object):
    """
    by default lazy loads the location
    TODO: add eager load option, joins on database.
    """

    def __init__(self, char_id, name, user_id, experience, lvl, location_id, weapon_id, armor_id, trait_id,
                 exp_gain_time, connection, location=None, weapon=None, armor=None, trait=None, special_ids=None,
                 specials=None):
        if special_ids is None:
            special_ids = []
        if specials is None:
            specials = []
        self.__char_id = char_id
        self.name = name
        self.user_id = user_id,
        self.experience = experience
        self.lvl = lvl
        self.exp_gain_time = exp_gain_time

        self.location_id = location_id
        self._location = location

        self.weapon_id = weapon_id
        self._weapon = weapon

        self.armor_id = armor_id
        self._armor = armor

        self.trait_id = trait_id  # This is a string
        self._trait = trait

        self.special_ids = special_ids  # This is a string
        self._specials = specials

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

    @weapon.setter
    def weapon(self, weapon):
        self._weapon = weapon
        self.weapon_id = weapon.id

    @property
    def armor(self):
        if self._armor is None:
            self._armor = Armor.find(self.armor_id)
        return self._armor

    @armor.setter
    def armor(self, armor):
        self._armor = armor
        self.armor_id = armor.id

    @property
    def trait(self):
        if self._trait is None:
            self._trait = Trait.find(self.trait_id)
        return self._trait

    @trait.setter
    def trait(self, trait):
        self._trait = trait
        self.trait_id = trait.id

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
    def find(cls, character_id, connection):
        cursor = connection.execute(
            """SELECT character_id, name, user_id, experience, lvl, location_id, weapon_id, armor_id from characters
            WHERE character_id = :character_id""",
            {"character_id": character_id}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

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
        """timestamp can be null, if stream goes offline for example"""
        Trait.create_table_if_not_exists(connection)
        Special.create_table_if_not_exists(connection)
        connection.execute(
            """create table if not exists characters
            (character_id integer PRIMARY KEY   NOT NULL,
            name            text    NOT NULL,
            user_id         text    UNIQUE ,
            experience      integer NOT NULL,
            lvl             integer NOT NULL,
            location_id     integer NOT NULL,
            weapon_id       integer NOT NULL,
            armor_id        integer NOT NULL,
            trait_id        text    NOT NULL,
            exp_gain_time   timestamp,
              FOREIGN KEY (location_id) REFERENCES locations(location_id),
              FOREIGN KEY (weapon_id)   REFERENCES weapons(weapon_id),
              FOREIGN KEY (armor_id)    REFERENCES armors(armor_id),
              FOREIGN KEY (trait_id)    REFERENCES trait(trait_id)
            );"""
        )


class Attack(object):
    def __init__(self, attack_id, attacker_id, target_id, resolve_time=None, resolver_id=None, connection=None,
                 children=None):
        if connection is None:
            raise ValueError("connection cannot be None")
        if children is None:
            children = []
        self.__attack_id = attack_id
        self.resolve_time = resolve_time
        self.connection = connection
        self.children = children

        self.attacker_id = attacker_id
        self._attacker = None

        self.target_id = target_id
        self._target = None

        self.resolver_id = resolver_id
        self._resolver = None

    @property
    def attack_id(self):
        return self.__attack_id

    @property
    def attacker(self):
        if self._attacker is None:
            self._attacker = Character.find(self.attack_id)
        return self._attacker

    @attacker.setter
    def attacker(self, attacker):
        self._attacker = attacker
        self.attacker_id = attacker.id

    @property
    def target(self):
        if self._target is None:
            self._target = Character.find(self.target_id)
        return self._target

    @target.setter
    def target(self, target):
        self._target = target
        self.target_id = target.id

    @property
    def resolver(self):
        if self._resolver is None and self.resolver_id is not None:
            self._resolver = Attack.find(self.resolver_id)
        return self._resolver

    @resolver.setter
    def resolver(self, resolver):
        self._resolver = resolver
        self.resolver_id = resolver.id

    def add_child(self, child):
        self.children.append(child)

    @classmethod
    def find_fights(cls, attack_id, connection):
        cursor = connection.execute(
            """SELECT Resolver.attack_id, Resolver.attacker_id, Resolver.target_id, Resolver.resolve_time,
            Child.attack_id, Child.attacker_id, Child.target_id, Child.resolver_id
            FROM attacks Resolver JOIN attacks Child on Child.resolver_id = Resolver.attack_id
            WHERE Resolver.resolve_time <= DATETIME('now')"""
        )
        fights = {}
        for row in cursor:
            if row[0] in fights:
                fights[row[0]].add_child(cls(*row[4:7], resolve_time=None, resolver_id=row[7], connection=connection))
            else:
                child = cls(*row[4:7], resolver_id=row[7], connection=connection)
                fights[row[0]] = cls(*row[:4], connection=connection, children=[child, ])
        return fights

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists attacks,
                        (attack_id      integer   PRIMARY KEY NOT NULL,
                        attacker_id     integer   NOT NULL,
                        target_id       integer   NOT NULL,
                        resolve_time    timestamp,
                        resolver_id       integer,
                         FOREIGN KEY (resolver_id)  REFERENCES attacks(attack_id)
                         FOREIGN KEY (attacker_id)  REFERENCES characters (character_id),
                         FOREIGN KEY (target_id)    REFERENCES characters (character_id)
                        );""")


class Trait(StaticData):
    def __init__(self, orig_name, name, connection):
        super(Trait, self).__init__(orig_name, name, connection)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists traits
                (orig_name      text PRIMARY KEY   NOT NULL,
                name            text  UNIQUE
                );""")


class Special(StaticData):
    """The specials self are static, the join-table won't be"""

    def __init__(self, orig_name, name, identifier, cooldown_time, connection):
        super(Special, self).__init__(orig_name, name, connection)
        self.cooldown_time = cooldown_time
        self.identifier = identifier

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists specials
            (orig_name      text PRIMARY KEY   NOT NULL,
            name            text NOT NULL,
            identifier      char, UNIQUE,
            cooldown_time   integer NOT NULL
            );""")

    @classmethod
    def load_specials(cls, connection):
        """loads weapons from database"""
        cursor = connection.execute('SELECT orig_name, name, identifier, cooldown_time FROM specials')
        for row in cursor:
            special = cls(*row, connection=connection)
            cls.data_by_id[special.id] = special
            cls.data_by_name[special.name] = special
