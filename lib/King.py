import characters
import datetime
from pytz import utc
import random
random = random.WichmannHill()


class Tournament(object):

    def __init__(self, end_time, tournament_id, connection=None):
        self.tournament_id = tournament_id
        self.end_time = end_time
        self.connection = connection

    def check_winner(self):
        part_count = Participant.count_alive_by_tournament(self, self.connection)
        if part_count == 1:
            return Participant.find_by_tournament_and_alive(self, self.connection)[0]
        if part_count == 0:
            self.delete()
            return None
        if self.end_time < datetime.datetime.now(utc):
            return random.choice(Participant.find_by_tournament_and_alive(self, self.connection))

    def delete(self):
        Participant.delete_by_tournament(self, self.connection)
        self.connection.execute("""DELETE FROM tournament WHERE tournament_id = ?""",
                                (self.tournament_id,))

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
        return cls(end_time, cursor.lastrowid, connection)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""
            CREATE TABLE IF NOT EXISTS tournament (
            end_time        timestamp,
            tournament_id   integer primary key NOT NULL 
            );""")
        Participant.create_table_if_not_exists(connection)

    @classmethod
    def initiate_tournament(cls, old_king, min_lvl, conn):
        tournament = cls.create(datetime.datetime.now(utc) + datetime.timedelta(minutes=10), conn)
        # find king and 2 or 3 top lvl
        participants = characters.Character.get_order_by_lvl_and_xp(3, conn, min_lvl=min_lvl)
        if old_king is not None and old_king.character is not None:
            if old_king.character not in participants:
                participants = participants[0:-1]
                participants.append(old_king.character)
        if len(participants) >= 2:
            for character in participants:
                Participant.create(character.char_id, True, tournament.tournament_id, conn)
            return participants
        return None


class Participant(object):
    """ participants have to fight each other, as long as they are participating they cannot be attacked by others, and
    they will not die from the tournament"""

    def __init__(self, character_id, alive, tournament_id, connection):
        self.character_id = character_id
        self.alive = alive
        self.tournament_id = tournament_id
        self.connection = connection

    def __eq__(self, other):
        if type(other) == Participant:
            return self.tournament_id == other.tournament_id
        return False

    def delete(self):
        self.connection.execute("""DELETE FROM participants WHERE character_id = ?""",
                                (self.character_id,))

    def save(self):
        self.connection.execute("""UPDATE participants SET alive = :alive WHERE character_id = :char_id""",
                                {"alive": self.alive, "char_id": self.character_id})

    @classmethod
    def delete_by_tournament(cls, tournament, connection):
        if type(tournament) == Tournament:
            tournament = tournament.tournament_id
        connection.execute("""DELETE FROM participants where tournament_id = ?""",
                           (tournament,))

    @classmethod
    def count_alive_by_tournament(cls, tournament, conn):
        if type(tournament) is Tournament:
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
    def find(cls, character_id, conn):
        cursor = conn.execute("""SELECT * from participants p WHERE p.character_id = ?""",
                              (character_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=conn)

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

    def __init__(self, tax_rate, character_id, gender, indisputable_until, connection, character=None):
        self.character_id = character_id

        self.tax_rate = tax_rate
        self.gender = gender
        self.indisputable_until = indisputable_until
        self.connection = connection
        self._character = character

    @property
    def character(self):
        if self._character is None:
            self._character = characters.Character.find(self.character_id, self.connection)
        return self._character

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
                old_king.indisputable_until = datetime.datetime.now(utc) + datetime.timedelta(minutes=30)
                old_king.save()
                return old_king
            else:
                old_king.delete()
        reign_time = datetime.datetime.now(utc) + datetime.timedelta(minutes=60)
        return King.create(5, participant.character_id, "king", reign_time, conn)

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
