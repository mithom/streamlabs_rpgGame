import characters
import datetime
from pytz import utc


class Tournament(object):

    def __init__(self, tournament_id, end_time, connection=None):
        self.tournament_id = tournament_id
        self.end_time = end_time
        self.connection = connection

    def check_winner(self):
        pass  # TODO: implement

    @classmethod
    def find(cls, conn):
        cursor = conn.execute("""select * from tournament limit 1""")
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=conn)

    @classmethod
    def create(cls, end_time, connection):
        cursor = connection.execute("""insert into tournament (end_time) values (?)""", (end_time,))
        return cls(cursor.lastrowid, end_time, connection)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""
            CREATE TABLE IF NOT EXISTS tournament (
            end_time        timestamp,
            tournament_id   integer primary key NOT NULL 
            );""")
        Participant.create_table_if_not_exists(connection)

    @classmethod
    def initiate_tournament(cls, old_king, conn):
        tournament = cls.create(datetime.datetime.now(utc) + datetime.timedelta(minutes=5), conn)
        # find king and 2 or 3 top lvl
        if old_king is not None and old_king.character is not None:
            Participant.create(old_king.character.char_id, True, tournament.tournament_id, conn)
            amount = 2
        else:
            amount = 3
        participants = characters.Character.get_order_by_lvl_and_xp(amount, conn)
        for character in participants:
            Participant.create(character.char_id, True, tournament.tournament_id, conn)


class Participant(object):
    """ participants have to fight each other, as long as they are participating they cannot be attacked by others, and
    they will not die from the tournament"""
    def __init__(self, character_id, alive, tournament_id, connection):
        self.character_id = character_id
        self.alive = alive
        self.tournament_id = tournament_id
        self.connection = connection

    @classmethod
    def create(cls, character_id, alive, tournament_id, connection):
        connection.execute("""INSERT INTO participants (character_id, alive, tournament_id)
            VALUES (:character_id, :alive, :tournament_id)""",
                           {"character_id": character_id, "alive": alive, "tournament_id":tournament_id})
        return cls(character_id, alive, tournament_id, connection)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""
            CREATE TABLE IF NOT EXISTS participants (
            character_id    integer NOT NULL primary key ,
            alive           boolean NOT NULL,
            tournament_id   integer NOT NULL ,
            FOREIGN KEY (tournament_id) REFERENCES tournament(tournament_id),
            FOREIGN KEY (character_id) REFERENCES characters(character_id)
            );""")


class King(object):
    current_king = None

    def __init__(self, character_id, tax_rate, gender, indisputable_until, connection):
        self.character_id = character_id

        self.tax_rate = tax_rate
        self.gender = gender
        self.indisputable_until = indisputable_until
        self.connection = connection
        self.character = None

    @classmethod
    def find(cls, conn):
        cursor = conn.execute("""select * from king limit 1""")
        row = cursor.fetchone()
        if row is None:
            return None
        king = cls(*row, connection=conn)
        king.character = characters.Character.find(king.character_id, conn)
        return king

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""
            CREATE TABLE IF NOT EXISTS king (
            tax_rate            integer,
            character_id        integer NOT NULL PRIMARY KEY ,
            gender              text,
            indisputable_until  timestamp NOT NULL ,
            FOREIGN KEY (character_id) REFERENCES characters(character_id)
            );""")
