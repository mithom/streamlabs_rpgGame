import characters
import datetime as dt
from pytz import utc
import Boss
import King
import Bounty


class Attack(object):
    ATTACK_ACTION = "attack"
    COUNTER_ACTION = "counter"
    DEFEND_ACTION = "defend"
    FLEE_ACTION = "flee"

    Parent = None
    format_message = None
    game = None

    def __init__(self, attack_id, action, attacker_id, target_id, resolve_time=None, resolver_id=None, boss_id=None,
                 connection=None, children=None):
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

        self._resolver_id = resolver_id
        self.resolver = None

        self.boss_id = boss_id

    @property
    def attack_id(self):
        return self.__attack_id

    @property
    def attacker(self):
        if self._attacker is None:
            self._attacker = characters.Character.find(self.attacker_id, self.connection)
        return self._attacker

    @attacker.setter
    def attacker(self, attacker):
        self._attacker = attacker
        self.attacker_id = attacker.id

    @property
    def target(self):
        if self._target is None:
            self._target = characters.Character.find(self.target_id, self.connection)
        return self._target

    @target.setter
    def target(self, target):
        self._target = target
        self.target_id = target.id

    @property
    def resolver_id(self):
        return self._resolver_id or self.attack_id

    @resolver_id.setter
    def resolver_id(self, resolver_id):
        self._resolver_id = resolver_id

    def resolve_fight(self):
        kills = {}
        defenders = [attack.attacker_id for attack in self.children if attack.action == self.DEFEND_ACTION]
        for attack in filter(lambda x: x.action == self.FLEE_ACTION, self.children):
            max_lvl = max(self.children, key=lambda x: x.attacker.lvl)
            max_lvl = max(max_lvl.attacker.lvl, self.attacker.lvl)
            if attack.attacker.attempt_flee(max_lvl):
                self.Parent.SendStreamMessage(self.format_message(
                    "{0} has successfully fled from the fight",
                    attack.attacker.name
                ))
        result = self.resolve_attack(self, kills, defenders)
        if result is not None:
            kills.update(result)
        for attack in self.children:
            result = self.resolve_attack(attack, kills, defenders, sneak=attack.action != self.COUNTER_ACTION)
            if result is not None:
                kills.update(result)
        self.delete()
        if len(kills) == 0:
            self.Parent.SendStreamMessage(self.format_message(
                "nobody died in the fight initiated by {0}",
                self.attacker.name
            ))
        for dead, killer in kills.iteritems():
            dead_char = characters.Character.find(dead, self.connection)
            killer_char = characters.Character.find(killer, self.connection)
            dead_part = King.Participant.find(dead_char.char_id, self.connection)
            if dead_part is not None and dead_part == King.Participant.find(killer_char.char_id, self.connection):
                self.Parent.SendStreamMessage(self.format_message(
                    "{0} has been knocked out of the tournament by {1}",
                    dead_char.name,
                    killer_char.name
                ))
                dead_part.alive = False
                dead_part.save()
            else:
                self.Parent.SendStreamMessage(self.format_message(
                    "{0} has been killed by {1} and died at lvl {2}",
                    dead_char.name,
                    killer_char.name,
                    dead_char.lvl
                ))
                if killer not in kills:
                    killer_char.gain_experience(2 * killer_char.exp_for_difficulty(dead_char.lvl))
                    killer_char.add_kill()
                    self.game.pay_bounties(Bounty.Bounty.find_all_by_character(dead, self.connection),
                                           killer_char.user_id)
                    killer_char.save()
                dead_char.delete()

    def resolve_attack(self, fight, kills, defenders, sneak=False):
        attacker = fight.attacker
        target = fight.target
        sneak = sneak and target not in defenders
        if target is None or target.char_id in kills or attacker.position != target.position:
            return None
        if attacker.attack(target, defense_bonus=attacker in defenders,
                           attack_bonus=fight.action == self.COUNTER_ACTION, sneak=sneak):
            return {target.char_id: attacker.char_id}
        else:
            return None

    def resolve_boss_attack(self):
        boss = Boss.Boss.find(self.boss_id, self.connection)
        if boss.state != boss.State.DEAD:
            if self.attacker.attack_boss(boss):
                self.attacker.gain_special()
            boss.save()
        self.delete()

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
    def create(cls, action, attacker_id, target_id=None, resolve_time=None, resolver_id=None, boss_id=None,
               connection=None):
        cursor = connection.execute('''INSERT INTO attacks (action, attacker_id, target_id, resolve_time, resolver_id,
                                    boss_id)
                                  VALUES (:action, :attacker_id, :target_id, :resolve_time, :resolver_id, :boss_id)''',
                                    {"action": action, "attacker_id": attacker_id, "target_id": target_id,
                                     "resolve_time": resolve_time, "resolver_id": resolver_id, "boss_id": boss_id}
                                    )
        connection.commit()
        return cls(cursor.lastrowid, action, attacker_id, target_id, resolve_time, resolver_id, connection=connection)

    @classmethod
    def find_fights(cls, connection):
        cursor = connection.execute(
            """SELECT Resolver.attack_id, Resolver.action, Resolver.attacker_id, Resolver.target_id,
            Resolver.resolve_time, Child.attack_id, Child.action, Child.attacker_id, Child.target_id, Child.resolver_id
            FROM attacks Resolver LEFT OUTER JOIN attacks Child on Child.resolver_id = Resolver.attack_id
            WHERE Resolver.resolve_time <= ? and Resolver.boss_id is null 
            ORDER BY Resolver.attack_id ASC, Child.attack_id ASC;""",
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
            """SELECT attack_id, action, attacker_id, target_id, resolve_time, resolver_id, boss_id
            FROM attacks
            WHERE attack_id = :attack_id """,
            {"attack_id": attack_id}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def find_boss_attack_past_resolve_time(cls, connection):
        cursor = connection.execute(
            """SELECT attack_id, action, attacker_id, target_id, resolve_time, resolver_id, boss_id
            FROM attacks
            WHERE boss_id is not null and resolve_time <= :now""",
            {"now": dt.datetime.now(utc)}
        )
        return map(lambda row: cls(*row, connection=connection), cursor)

    @classmethod
    def find_by_attacker_or_target(cls, attacker, connection):
        if type(attacker) is characters.Character:
            attacker = attacker.char_id
        cursor = connection.execute(
            """SELECT attack_id, action, attacker_id, target_id, resolve_time, resolver_id, boss_id
            FROM attacks
            WHERE attacker_id = :attacker_id or target_id = :attacker_id
            ORDER BY attacker_id = :attacker_id DESC """,
            {"attacker_id": attacker}
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls(*row, connection=connection)

    @classmethod
    def find_by_target(cls, target, connection):
        if type(target) is characters.Character:
            target = target.char_id
        cursor = connection.execute(
            """SELECT attack_id, action, attacker_id, target_id, resolve_time, resolver_id, boss_id
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
                        boss_id         integer,
                        resolve_time    timestamp,
                        resolver_id     integer,
                         FOREIGN KEY (resolver_id)  REFERENCES attacks(attack_id),
                         FOREIGN KEY (attacker_id)  REFERENCES characters (character_id),
                         FOREIGN KEY (target_id)    REFERENCES characters (character_id),
                         FOREIGN KEY (boss_id)      REFERENCES bosses(boss_id)
                        );""")
