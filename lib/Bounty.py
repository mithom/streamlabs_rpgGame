import characters


class Bounty(object):
    def __init__(self, bounty_id, character_id, benefactor_id, reward, kill_count, connection):
        self.connection = connection
        self.__bounty_id = bounty_id
        self._reward = reward
        self.kill_count = kill_count

        self.character_id = character_id
        self._character = None

        self.benefactor_id = benefactor_id
        self._benefactor = None

        self.__calculated = False

    @property
    def id(self):
        return self.__bounty_id

    @property
    def character(self):
        if self._character is None:
            self._character = characters.Character.find(self.character_id, self.connection)
        return self._character

    @character.setter
    def character(self, value):
        self._character = value
        self.character_id = value.char_id

    @property
    def benefactor(self):
        if self._benefactor is None and self.benefactor_id is not None:
            self._benefactor = characters.Character.find(self.benefactor_id, self.connection)
        return self._benefactor

    @benefactor.setter
    def benefactor(self, value):
        self._benefactor = value
        self.benefactor_id = value.char_id

    @staticmethod
    def kill_reward(kill_count):
        return kill_count * 100 + max(300*2**(max(kill_count, 0)/3)-300, 0)

    @property
    def reward(self):
        if self.kill_count is not None and not self.__calculated:
            self._reward += self.kill_reward(self.kill_count)
            self.__calculated = True
        return self._reward

    @reward.setter
    def reward(self, reward):
        self._reward = reward

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
            {"character_id": self.character_id, "benefactor_id": self.benefactor_id, "reward": self._reward,
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
    def find_by_user_id_from_piebank(cls, user_id, connection):
        cursor = connection.execute(
            """SELECT b.* from bounties b natural join characters c
            WHERE  c.user_id = :user_id and b.benefactor_id is NULL """,
            {"user_id": user_id}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def find_by_character_name_and_benefactor(cls, char_name, benefactor_id, connection):
        if type(benefactor_id) is characters.Character:
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
        if type(character) is characters.Character:
            character = character.char_id
        cursor = conn.execute("""SELECT * FROM bounties WHERE character_id = :character_id""",
                              {"character_id": character})
        return [cls(*row, connection=conn) for row in cursor]

    @classmethod
    def find_all_ordered_by_worth(cls, page, per, conn):
        """bounty_id and benefactor_id will be a random, this is just to make the init work"""
        # cursor = conn.execute("""SELECT bounty_id, character_id, benefactor_id,sum(reward), sum(kill_count)
        #                       FROM bounties
        #                       GROUP BY character_id
        #                       ORDER BY sum(reward) DESC LIMIT :limit OFFSET :offset""",
        #                       {"limit": per, "offset": (page-1)*per})
        conn.create_function("KILLREWARD", 1, cls.kill_reward)
        cursor = conn.execute('''SELECT bounty_id, character_id, benefactor_id,sum(reward), sum(kill_count)
                              FROM bounties
                              GROUP BY character_id
                              ORDER BY sum(reward)+ KILLREWARD(IFNULL(sum(kill_count),0))
                              DESC LIMIT :limit OFFSET :offset''',
                              {"limit": per, "offset": (page - 1) * per})
        return [cls(*row, connection=conn) for row in cursor]

    @classmethod
    def find_all_ordered_by_kills(cls, page, per, conn):
        cursor = conn.execute("""SELECT * FROM bounties WHERE benefactor_id IS NULL
                              ORDER BY kill_count DESC LIMIT :limit OFFSET :offset""",
                              {"limit": per, "offset": (page-1)*per})
        return [cls(*row, connection=conn) for row in cursor]

    @staticmethod
    def count(conn, only_kills=False):
        if only_kills:
            cursor = conn.execute("""SELECT COUNT(DISTINCT character_id) FROM bounties WHERE benefactor_id IS NULL""")
        else:
            cursor = conn.execute("""SELECT COUNT(DISTINCT character_id) FROM bounties """)
        return cursor.fetchone()[0]

    @classmethod
    def create(cls, character, benefactor, reward, kill_count, connection):
        if type(character) is characters.Character:
            character = character.char_id
        if type(benefactor) is characters.Character:
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
        kill_count    integer,
        FOREIGN KEY (benefactor_id) REFERENCES characters(character_id),
        FOREIGN KEY (character_id) REFERENCES characters(character_id)
        );""")
