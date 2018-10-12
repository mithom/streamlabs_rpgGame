import characters


class Tournament(object):

    def __init__(self, _id, end_time, connection=None, *participants):
        self.__id = _id
        self.end_time = end_time
        self.participants = participants
        self.connection = connection

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""
            CREATE TABLE IF NOT EXISTS tournament (
            end_time      timestamp,
            tournament_id            integer primary key NOT NULL 
            );""")
        Participant.create_table_if_not_exists(connection)


class Participant(object):
    def __init__(self, character_id, alive, tournament_id):
        self.character_id = character_id
        self.alive = alive
        self.tournament_id = tournament_id

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

    def __init__(self, character_id, tax_rate, gender, indisputable_until):
        self.character_id = character_id

        self.tax_rate = tax_rate
        self.gender = gender
        self.indisputable_until = indisputable_until

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
