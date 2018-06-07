from characters import Character


class Bounty(object):
    def __init__(self, bounty_id, character_id, benefactor_id, reward, kill_count, connection):
        self.connection = connection
        self.__bounty_id = bounty_id
        self.reward = reward
        self.kill_count = kill_count

        self.character_id = character_id
        self._character = None

        self.benefactor_id = benefactor_id
        self._benefactor = None

    @property
    def id(self):
        return self.__bounty_id

    @property
    def character(self):
        if self._character is None:
            self._character = Character.find(self.character_id, self.connection)
        return self._character

    @character.setter
    def character(self, value):
        self._character = value
        self.character_id = value.char_id

    @property
    def benefactor(self):
        if self._benefactor is None and self.benefactor_id is not None:
            self._benefactor = Character.find(self.benefactor_id, self.connection)
        return self._benefactor

    @benefactor.setter
    def benefactor(self, value):
        self._benefactor = value
        self.benefactor_id = value.char_id

    def delete(self):
        self.connection.execute(
            """DELETE FROM bounties WHERE
            bounty_id = :bounty_id""",
            {"bounty_id": self.id}
        )

    def save(self):
        self.connection.execute(
            """UPDATE bounties set
            character_id = :character_id, benefactor_id = :benefactor_id, reward = :reward, kill_count = :kill_count
            WHERE bounty_id = :bounty_id""",
            {"character_id": self.character_id, "benefactor_id": self.benefactor_id, "reward": self.reward,
                "kill_count": self.kill_count, "bounty_id": self.id}
        )

    @classmethod
    def find(cls, bounty_id, connection):
        cursor = connection.execute(
            """SELECT * from bounties WHERE bounty_id = :bounty_id""",
            {"bounty_id": bounty_id}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)


    @classmethod
    def find_by_character_name_from_piebank(cls, char_name, connection):
        cursor = connection.execute(
            """SELECT b.* from bounties b natural join characters c
            WHERE  c.name = :character_name and b.benefactor_id is NULL """,
            {"character_name": char_name}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def find_by_character_name_and_benefactor(cls, char_name, benefactor_id, connection):
        if type(benefactor_id) is Character:
            benefactor_id = benefactor_id.char_id
        cursor = connection.execute(
            """SELECT b.* from bounties b natural join characters c
            WHERE  c.name = :character_name and b.benefactor_id = :benefactor_id""",
            {"character_name": char_name, "benefactor_id": benefactor_id}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def find_all_by_character(cls, character, conn):
        if type(character) is Character:
            character = character.char_id
        cursor = conn.execute("""SELECT * FROM bounties WHERE character_id = :character_id""",
                              {"character_id": character})
        return [cls(*row, connection=conn) for row in cursor]

    @classmethod
    def create(cls, character, benefactor, reward, kill_count, connection):
        if type(character) is Character:
            character = character.char_id
        if type(benefactor) is Character:
            benefactor = benefactor.char_id
        cursor = connection.execute(
            """INSERT INTO bounties (character_id, benefactor_id, reward, kill_count) VALUES 
            (:character_id, :benefactor_id, :reward, :kill_count)
            """,
            {"character_id": character, "benefactor_id": benefactor, "reward": reward, "kill_count": kill_count}
        )
        connection.commit()
        return cls(cursor.lastrowid, character, benefactor, reward, kill_count, connection=connection)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""
        CREATE TABLE IF NOT EXISTS bounties (
        bounty_id     integer PRIMARY KEY   NOT NULL,
        character_id  integer NOT NULL ,
        benefactor_id integer,
        reward        integer NOT NULL,
        kill_count         integer,
        FOREIGN KEY (benefactor_id) REFERENCES characters(character_id),
        FOREIGN KEY (character_id) REFERENCES characters(character_id)
        );""")
