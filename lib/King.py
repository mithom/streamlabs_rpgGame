import characters
import datetime
from pytz import utc


class Tournament(object):

    def __init__(self, tournament_id, end_time, connection=None):
        self.tournament_id = tournament_id
        self.end_time = end_time
        self.connection = connection

    def check_winner(self):
        part_count = Participant.count_alive_by_tournament(self, self.connection)
        if part_count == 1:
            return Participant.find_by_tournament_and_alive(self, self.connection)[0]
        return None

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
    def count_alive_by_tournament(cls, tournament, conn):
        if type(tournament) == Tournament:
            tournament = tournament.tournament_id
        cursor = conn.execute("""select count(*) from participants p where p.tournament_id = ? and p.alive = 1""",
                              (tournament,))
        return cursor.fetchone()[0]

    @classmethod
    def find_by_tournament_and_alive(cls, tournament, conn):
        if type(tournament) == Tournament:
            tournament = tournament.tournament_id
        cursor = conn.execute("""SELECT * FROM participants p
          WHERE p.tournament_id = ? and p.alive = 1""", (tournament,))
        return map(lambda row: cls(*row, connection=conn), cursor)

    @classmethod
    def create(cls, character_id, alive, tournament_id, connection):
        connection.execute("""INSERT INTO participants (character_id, alive, tournament_id)
            VALUES (:character_id, :alive, :tournament_id)""",
                           {"character_id": character_id, "alive": alive, "tournament_id": tournament_id})
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

    def __init__(self, tax_rate, character_id, gender, indisputable_until, connection):
        self.character_id = character_id

        self.tax_rate = tax_rate
        self.gender = gender
        self.indisputable_until = indisputable_until
        self.connection = connection
        self.character = None

    def delete(self):
        self.connection.execute("""DELETE FROM king WHERE king.character_id = ?""",
                                (self.character_id,))

    def save(self):
        self.connection.execute("""UPDATE king set tax_rate = :tax_rate, gender = :gender,
            indisputable_until = :indisp_until WHERE king.character_id = :char_id""",
                                {"tax_rate": self.tax_rate, "gender": self.gender,
                                 "indisp_until": self.indisputable_until, "char_id": self.character_id})

    @classmethod
    def crown(cls, participant, conn):
        old_king = cls.find(conn)
        if old_king is not None:
            if old_king.character_id == participant.character_id:
                old_king.indisputable_until = datetime.datetime.now(utc) + datetime.timedelta(minutes=60)
                old_king.save()
            else:
                old_king.delete()
                reign_time = datetime.datetime.now(utc) + datetime.timedelta(minutes=60)
                King.create(5, participant.character_id, "king", reign_time, conn)

    @classmethod
    def create(cls, tax_rate, character_id, gender, indisputable_until, conn):
        conn.execute("""INSERT INTO king (tax_rate, character_id, gender, indisputable_until) 
            values (:tax_rate, :char_id, :gender, :indisp_until)""",
                     {"tax_rate": tax_rate, "char_id": character_id, "gender": gender,
                      "indisp_until": indisputable_until})
        return cls(tax_rate, character_id, gender, indisputable_until, conn)

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
