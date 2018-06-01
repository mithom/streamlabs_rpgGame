from StaticData import Location, Weapon, Armor
from characters import Character, Trait
from Attack import Attack

import os
import datetime as dt
from pytz import utc

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
            Trait.create_traits(self.scriptSettings, conn)
            Character.load_static_data(conn)

    def apply_reload(self):
        pass

    def tick(self):
        with self.get_connection() as conn:
            for fight in Attack.find_fights(conn):
                self.resolve_fight(fight)
            lvl_up = []
            for character in Character.find_by_past_exp_time(conn):
                character.exp_gain_time = dt.datetime.now(utc) + dt.timedelta(seconds=self.scriptSettings.xp_farm_time)
                if character.gain_experience():
                    lvl_up.append(character)
                character.save()  # TODO: batch update
            if len(lvl_up) > 0:
                Parent.SendStreamMessage(self.format_message(
                    "some characters just lvl'ed up: " + ", ".join(map(lambda char: char.name, lvl_up))
                ))

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
            self.scriptSettings.create_command: self.create,
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
            if character is None:
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
                return
            location = character.location
            Parent.SendStreamMessage(self.format_message(
                "{0}, your character {1} is located in {2} with difficulty {3}. Your current lvl is {4} and xp {5}. " +
                "Your current are currently wearing {6} and use {7} as weapon",
                username,
                character.name,
                location.name,
                location.difficulty,
                character.lvl,
                character.experience,
                getattr(character.armor, "name", "rags"),
                getattr(character.weapon, "name", "bare hands")
            ))

    def condensed_info(self, user_id, username):
        with self.get_connection() as conn:
            character = Character.find_by_user(user_id, conn)
            if character is None:
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
                return
            Parent.SendStreamMessage(self.format_message(
                "{0}, name: {1}, location {2}, lvl: {3}",
                username,
                character.name,
                character.location.name,
                character.lvl
            ))

    def create(self, user_id, username, character_name):
        with self.get_connection() as conn:
            if Character.find_by_user(user_id, conn) is None and Character.find_by_name(character_name, conn) is None:
                town = Location.find_by_name(self.scriptSettings.starting_location)
                exp_gain_time = dt.datetime.now(utc) + dt.timedelta(seconds=self.scriptSettings.xp_farm_time)
                Character.create(character_name, user_id, 0, 1, town.id, None, None, exp_gain_time, conn)
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you just created a new hero who listens to the mighty name of {1}. For more info about this" +
                    " hero, type " + self.scriptSettings.info_command,
                    username,
                    character_name
                ))
            else:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, character could not be created, you either already have one, or {1} has been taken",
                    username,
                    character_name
                ))

    def move(self, user_id, username, location_name):
        with self.get_connection() as conn:
            location = Location.find_by_name(location_name)
            character = Character.find_by_user(user_id, conn)
            if character is None:
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
                return
            if character.location_id != character.location_id:
                character.location = location
                character.exp_gain_time = dt.datetime.now(utc) + dt.timedelta(seconds=self.scriptSettings.xp_farm_time)
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
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
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
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
                return
            if target is None:
                Parent.SendStreamMessage(
                    self.format_message("{0}, no target exists with that character name", username))
                return
            if target.location_id == attacker.location_id:
                fight = Attack.find_by_attacker(target, conn)
                attacker.exp_gain_time += dt.timedelta(seconds=self.scriptSettings.fight_resolve_time)
                attacker.save()
                if fight is None:
                    resolve_time = dt.datetime.now(utc) + dt.timedelta(seconds=self.scriptSettings.fight_resolve_time)
                    Attack.create(self.ATTACK_ACTION, attacker.char_id, target.char_id, resolve_time, connection=conn)
                    target.exp_gain_time += dt.timedelta(seconds=self.scriptSettings.fight_resolve_time)
                    target.save()
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
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
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
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
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
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
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
        with self.get_connection() as conn:
            target_char = Character.find_by_name(target_name, conn)
            user_char = Character.find_by_user(user_id, conn)
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
                with self.get_connection() as conn:
                    recipient = Character.find_by_name(recipient_name, conn)
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
