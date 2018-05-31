from StaticData import Location, Weapon, Armor
from characters import Character
from Attack import Attack

import os
import datetime as dt

import clr

clr.AddReference("IronPython.SQLite.dll")
import sqlite3

Parent = None


class RpgGame(object):
    ATTACK_ACTION = "attack"
    COUNTER_ACTION = "counter"
    DEFEND_ACTION = "defend"
    FLEE_ACTION = "flee"

    def __init__(self, script_settings, script_name, db_directory):
        self.scriptSettings = script_settings
        self.script_name = script_name
        self.db_directory = db_directory

        # Prepare everything
        self.prepare_database()
        self.create_and_load_static_data()

        Character.game = self

    def get_connection(self):
        return sqlite3.connect(os.path.join(self.db_directory, "database.db"), detect_types=sqlite3.PARSE_DECLTYPES)

    def prepare_database(self):
        with self.get_connection() as conn:
            # create all tables, location first, because character got foreign key to this
            Location.create_table_if_not_exists(conn)
            Weapon.create_table_if_not_exists(conn)
            Armor.create_table_if_not_exists(conn)
            Character.create_table_if_not_exists(conn)
            Attack.create_table_if_not_exists(conn)

    def create_and_load_static_data(self):
        with self.get_connection() as conn:
            Location.create_locations(self.scriptSettings, conn)
            Location.load_locations(conn)
            Armor.load_armors(conn)
            Weapon.load_weapons(conn)
            Character.load_static_data(conn)

    def apply_reload(self):
        pass

    def tick(self):

        with self.get_connection() as conn:
            for fight in Attack.find_fights(conn):
                self.resolve_fight(fight)
            # TODO: retrieve user who deserve xp

    def resolve_fight(self, fight):
        pass  # TODO: implement

    def commands(self):
        # TODO: create or join command (with name param)
        return [{
            self.scriptSettings.info_command: self.info,
            self.scriptSettings.condensed_info_command: self.condensed_info,
            self.scriptSettings.stat_command: self.stat,
            self.scriptSettings.defend_command: self.defend,
            self.scriptSettings.counter_command: self.counter,
            self.scriptSettings.flee_command: self.flee,
            self.scriptSettings.dough_command: self.dough,
            self.scriptSettings.queen_command: self.queen,
            self.scriptSettings.king_command: self.king
        }, {
            self.scriptSettings.move_command: self.move,
            self.scriptSettings.buy_command: self.buy,
            self.scriptSettings.attack_command: self.attack,
            self.scriptSettings.look_command: self.look,
            self.scriptSettings.tax_command: self.tax,
            self.scriptSettings.vote_command: self.vote,
            self.scriptSettings.smite_command: self.smite,
            self.scriptSettings.unsmite_command: self.unsmite,
        }, {
            self.scriptSettings.give_command: self.give,
            self.scriptSettings.bounty_command: self.bounty,
        }]

    def info(self, user_id, username):
        with self.get_connection() as conn:
            character = Character.find_by_user(user_id, conn)
            location = character.location
            Parent.SendStreamMessage(self.format_message(
                "{0}, your character {1} is located in {2} with difficulty {3}",
                username,
                character.name,
                location.name,
                location.difficulty
            ))

    def condensed_info(self, user_id, username):
        with self.get_connection() as conn:
            character = Character.find_by_user(user_id, conn)
            Parent.SendStreamMessage(self.format_message(
                "{0}, your character {1} is located in {2}",
                username,
                character.name,
                character.location.name
            ))

    def move(self, user_id, username, location_name):
        with self.get_connection() as conn:
            location = Location.find_by_name(location_name)
            character = Character.find_by_user(user_id, conn)
            if character is None:
                Parent.SendStreamMessage(self.format_message(self.scriptSettings.no_character_yet, username))
                return
            if character.location_id != character.location_id:
                character.location = location
                character.save()
                Parent.SendStreamMessage(self.format_message(
                    "{0}, {1} moved to location {2} with difficulty {3}",
                    username,
                    character.name,
                    location.name,
                    location.difficulty
                ))

    def buy(self, user_id, username, item_name):
        with self.get_connection() as conn:
            character = Character.find_by_user(user_id, conn)
            if character is None:
                Parent.SendStreamMessage(self.format_message(self.scriptSettings.no_character_yet, username))
                return
            weapon = Weapon.find_by_name(item_name)
            if weapon is not None:
                if character.lvl >= weapon.min_lvl and Parent.RemovePoints(user_id, username, weapon.price):
                    character.weapon = weapon
                    character.save()
            else:
                armor = Armor.find_by_name(item_name)
                if armor is not None:
                    if character.lvl >= weapon.min_lvl and Parent.RemovePoints(user_id, username, armor.price):
                        character.armor = armor
                        character.save()
                else:
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, {1} does not exists",
                        username,
                        item_name
                    ))

    def attack(self, user_id, username, target_name):
        with self.get_connection() as conn:
            target = Character.find_by_name(target_name, conn)
            attacker = Character.find_by_user(user_id, conn)
            if attacker is None:
                Parent.SendStreamMessage(self.format_message(self.scriptSettings.no_character_yet, username))
                return
            if target is None:
                Parent.SendStreamMessage(
                    self.format_message("{0}, no target exists with that character name", username))
                return
            if target.location_id == attacker.location_id:
                fight = Attack.find_by_attacker(target, conn)
                if fight is None:
                    resolve_time = dt.datetime.today() + dt.timedelta(seconds=self.scriptSettings.fight_resolve_time)
                    Attack.create(self.ATTACK_ACTION, attacker.char_id, target.char_id, resolve_time, connection=conn)
                else:
                    if fight.resolver_id is None:
                        resolver_id = fight.attack_id
                    else:
                        resolver_id = fight.resolver_id
                    Attack.create(self.ATTACK_ACTION, attacker.char_id, target.char_id, resolver_id=resolver_id,
                                  connection=conn)

    def defend(self, user_id, username):
        with self.get_connection() as conn:
            defender = Character.find_by_user(user_id, conn)
            if defender is None:
                Parent.SendStreamMessage(self.format_message(self.scriptSettings.no_character_yet, username))
                return
            fight = Attack.find_by_target(defender, conn)
            if fight is None:
                Parent.SendStreamMessage("you are currently not being attacked")
                return
            else:
                if fight.resolver_id is None:
                    resolver_id = fight.attack_id
                else:
                    resolver_id = fight.resolver_id
                Attack.create(self.DEFEND_ACTION, defender.char_id, resolver_id=resolver_id, connection=conn)

    def counter(self, user_id, username):
        with self.get_connection() as conn:
            counterer = Character.find_by_user(user_id, conn)
            if counterer is None:
                Parent.SendStreamMessage(self.format_message(self.scriptSettings.no_character_yet, username))
                return
            fight = Attack.find_by_target(counterer, conn)
            if fight is None:
                Parent.SendStreamMessage("you are currently not being attacked")
                return
            else:
                if fight.resolver_id is None:
                    resolver_id = fight.attack_id
                else:
                    resolver_id = fight.resolver_id
                Attack.create(self.COUNTER_ACTION, counterer.char_id, resolver_id=resolver_id, connection=conn)

    def flee(self, user_id, username):
        with self.get_connection() as conn:
            flee_char = Character.find_by_user(user_id, conn)
            if flee_char is None:
                Parent.SendStreamMessage(self.format_message(self.scriptSettings.no_character_yet, username))
                return
            fight = Attack.find_by_target(flee_char, conn)
            if fight is None:
                Parent.SendStreamMessage("you are currently not being attacked")
                return
            else:
                if fight.resolver_id is None:
                    resolver_id = fight.attack_id
                else:
                    resolver_id = fight.resolver_id
                Attack.create(self.FLEE_ACTION, flee_char.char_id, resolver_id=resolver_id, connection=conn)

    def look(self, user_id, username, target_name):
        target_char = Character.find_by_name(target_name)
        user_char = Character.find_by_user(user_id)
        # TODO: compare

    def dough(self, user_id, username):
        Parent.SendStreamMessage(self.format_message("{0}, your current piecoin balance is {1} {2}",
                                                     username,
                                                     Parent.GetPoints(user_id),
                                                     Parent.GetCurrencyName()
                                                     ))

    def give(self, user_id, username, amount, recipient_name):
        if recipient_name == self.scriptSettings.piebank_name:
            if Parent.RemovePoints(user_id, username, amount):
                # TODO: check bounty (and create bounties)
                pass
            else:
                recipient = Character.find_by_name(recipient_name)
                if Parent.RemovePoints(user_id, username, amount):
                    recipient_user_name = Parent.GetDisplayName(recipient.user_id)
                    if Parent.AddPoints(recipient.user_id, recipient_user_name, amount):
                        Parent.SendStreamMessage(self.format_message("{0} just gave {1} {2} {3}",
                                                                     username,
                                                                     recipient_user_name,
                                                                     amount,
                                                                     Parent.GetCurrencyName()
                                                                     ))
                    else:
                        Parent.AddPoints(user_id, username, amount)

    def bounty(self, user_id, username, amount, target_name):
        pass

    def tax(self, user_id, username, amount):
        pass

    def queen(self, user_id, username):
        pass

    def king(self, user_id, username):
        pass

    def vote(self, user_id, username, target_name):
        pass

    def smite(self, user_id, username, target_name):
        pass

    def unsmite(self, user_id, username, target_name):
        pass

    def stat(self, user_id, username):
        pass

    # ---------------------------------------
    #   auxiliary functions
    # ---------------------------------------
    def format_message(self, msg, *args):
        if self.scriptSettings.add_me:
            msg = "/me " + msg
        return msg.format(*args)
