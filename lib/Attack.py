from characters import Character
import datetime as dt
from pytz import utc


class Attack(object):
    def __init__(self, attack_id, action, attacker_id, target_id, resolve_time=None, resolver_id=None, connection=None,
                 children=None):
        if connection is None:
            raise ValueError("connection cannot be None")
        if children is None:
            children = []
        self.__attack_id = attack_id
        if resolve_time is not None and resolve_time.tzinfo is None:
            resolve_time = utc.localize(resolve_time)
        self.resolve_time = resolve_time
        self.connection = connection
        self.action = action
        self.children = []
        for child in children:
            self.add_child(child)

        self.attacker_id = attacker_id
        self._attacker = None

        self.target_id = target_id
        self._target = None

        self.resolver_id = resolver_id
        self.resolver = None

    @property
    def attack_id(self):
        return self.__attack_id

    @property
    def attacker(self):
        if self._attacker is None:
                self._attacker = Character.find(self.attacker_id, self.connection)
        return self._attacker

    @attacker.setter
    def attacker(self, attacker):
        self._attacker = attacker
        self.attacker_id = attacker.id

    @property
    def target(self):
        if self._target is None:
            self._target = Character.find(self.target_id, self.connection)
        return self._target

    @target.setter
    def target(self, target):
        self._target = target
        self.target_id = target.id

    def add_child(self, child):
        assert child.resolver_id == self.attack_id
        self.children.append(child)
        child.resolver = self

    def delete(self):
        self.connection.execute(
            """DELETE FROM attacks
            WHERE resolver_id = ?""",
            (self.attack_id,)
         )
        self.connection.execute(
            """DELETE FROM attacks
            WHERE attack_id = ?""",
            (self.attack_id,)
        )

    @classmethod
    def create(cls, action, attacker_id, target_id=None, resolve_time=None, resolver_id=None, connection=None):
        cursor = connection.execute('''INSERT INTO attacks (action, attacker_id, target_id, resolve_time, resolver_id)
                                    VALUES (:action, :attacker_id, :target_id, :resolve_time, :resolver_id)''',
                                    {"action": action, "attacker_id": attacker_id, "target_id": target_id,
                                     "resolve_time": resolve_time, "resolver_id": resolver_id}
                                    )
        connection.commit()
        return cls(cursor.lastrowid, action, attacker_id, target_id, resolve_time, resolver_id, connection=connection)

    @classmethod
    def find_fights(cls, connection):
        cursor = connection.execute(
            """SELECT Resolver.attack_id, Resolver.action, Resolver.attacker_id, Resolver.target_id,
            Resolver.resolve_time, Child.attack_id, Child.action, Child.attacker_id, Child.target_id, Child.resolver_id
            FROM attacks Resolver LEFT OUTER JOIN attacks Child on Child.resolver_id = Resolver.attack_id
            WHERE Resolver.resolve_time <= ?
            ORDER BY Resolver.attack_id ASC, Child.attack_id;""",
            (dt.datetime.now(utc),)
        )
        fights = {}
        for row in cursor:
            if row[0] in fights:
                fights[row[0]].add_child(cls(*row[5:9], resolver_id=row[9], connection=connection))
            else:
                if row[5] is None:
                    fights[row[0]] = cls(*row[:5], connection=connection)
                else:
                    child = cls(*row[5:9], resolver_id=row[9], connection=connection)
                    fights[row[0]] = cls(*row[:5], connection=connection, children=[child])
        return fights.values()

    @classmethod
    def find(cls, attack_id, connection):
        cursor = connection.execute(
            """SELECT attack_id, action, attacker_id, target_id, resolve_time, resolver_id
            FROM attacks
            WHERE attack_id = :attack_id """,
            {"attack_id": attack_id}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def find_by_attacker_or_target(cls, attacker, connection):
        if type(attacker) is Character:
            attacker = attacker.char_id
        cursor = connection.execute(
            """SELECT attack_id, action, attacker_id, target_id, resolve_time, resolver_id
            FROM attacks
            WHERE attacker_id = :attacker_id or target_id = :attacker_id""",
            {"attacker_id": attacker}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def find_by_target(cls, target, connection):
        if type(target) is Character:
            target = target.char_id
        cursor = connection.execute(
            """SELECT attack_id, action, attacker_id, target_id, resolve_time, resolver_id
            FROM attacks
            WHERE target_id = :target_id""",
            {"target_id": target}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def create_table_if_not_exists(cls, connection):
        connection.execute("""create table if not exists attacks
                        (attack_id      integer   PRIMARY KEY   NOT NULL,
                        action          text      NOT NULL,
                        attacker_id     integer   NOT NULL,
                        target_id       integer,
                        resolve_time    timestamp,
                        resolver_id     integer,
                         FOREIGN KEY (resolver_id)  REFERENCES attacks(attack_id),
                         FOREIGN KEY (attacker_id)  REFERENCES characters (character_id),
                         FOREIGN KEY (target_id)    REFERENCES characters (character_id)
                        );""")
