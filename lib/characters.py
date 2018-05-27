from StaticData import Location


class Character(object):
    """
    by default lazy loads the location
    TODO: add eager load option, joins on database.
    """
    def __init__(self, char_id, name, user_id, location_id, connection, location=None):
        self.__char_id = char_id
        self.name = name
        self.user_id = user_id,
        self.location_id = location_id
        self.connection = connection
        self._location = location

    @property
    def char_id(self):
        return self.__char_id

    @property
    def location(self):
        if self._location is None:
            self._location = Location.find(self.char_id)
        return self._location

    @location.setter
    def location(self, location):
        self._location = location
        self.location_id = location.id

    def save(self):
        self.connection.execute(
            """UPDATE characters set location_id = :location_id, name = :name, user_id = :user_id
            where char_id = :char_id""",
            location_id=self.location_id, name=self.name, user_id=self.user_id, char_id=self.char_id,
        )
        self.connection.commit()

    @classmethod
    def create(cls, name, user_id, location_id, connection):
        cursor = connection.execute('''INSERT INTO Characters (name, user_id, location_id)
                                        VALUES (:name, :user_id, :location_id)''',
                                    {"name": name, "user_id": user_id, "location_id": location_id})
        connection.commit()
        return cls(cursor.lastrowid, name, user_id, location_id, connection=connection)

    @classmethod
    def find_by_user(cls, user_id, connection):
        cursor = connection.execute(
            """SELECT character_id, name, user_id, location_id from characters
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
            location_id     integer NOT NULL,
              FOREIGN KEY (location_id) REFERENCES locations(location_id)
            );"""
        )


class Boss(object):
    def __init__(self):
        pass


class Roshan(Boss):
    def __init__(self):
        super(Roshan, self).__init__()
        pass


class Traits(object):
    def __init__(self):
        pass


class Specials(object):
    def __init__(self):
        pass
