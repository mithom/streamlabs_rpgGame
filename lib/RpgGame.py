from StaticData import Location, Weapon, Armor
from characters import Character, Trait
from Attack import Attack

import os
import datetime as dt
from pytz import utc
import time

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
                self.resolve_fight(fight, conn)
            lvl_up = []
            deaths = []
            characters = Character.find_by_past_exp_time(conn)
            coin_rewards = {}
            for character in characters:
                if character.check_survival():
                    coin_rewards[character.user_id] = character.location.difficulty
                    character.exp_gain_time = dt.datetime.now(utc) + dt.timedelta(
                        seconds=self.scriptSettings.xp_farm_time)
                    if character.gain_experience(character.exp_for_difficulty(character.location.difficulty)):
                        lvl_up.append(character)
                    character.save()  # TODO: batch update
                else:
                    deaths.append(character)
                    character.delete()
            Parent.AddPointsAll(coin_rewards)
            conn.commit()
            if len(lvl_up) > 0:
                Parent.SendStreamMessage(self.format_message(
                    "some characters just lvl'ed up: " + ", ".join(map(lambda char: char.name, lvl_up))
                ))
            if len(deaths) > 0:
                Parent.SendStreamMessage(self.format_message(
                    "some characters died while roaming the dangerous lands or pieland: " +
                    ", ".join(map(lambda char: char.name, deaths))
                ))

    def resolve_fight(self, fight, conn):  # TODO: kill count + bounties
        # resolve initial fight
        attacker = fight.attacker
        target = fight.target
        assert fight.action == self.ATTACK_ACTION
        reaction = next((attack for attack in fight.children if target.char_id == attack.attacker_id), None)
        defense = reaction is not None and reaction.action == self.DEFEND_ACTION
        flee = reaction is not None and reaction.action == self.FLEE_ACTION
        success1, flee = attacker.attack(target, defense_bonus=defense, flee=flee)
        success2 = False
        if reaction is not None and reaction.action == self.COUNTER_ACTION:
            success2 = target.attack(attacker, attack_bonus=True)[0]
            if success2:
                attacker.delete()
                if not success1:
                    target.gain_experience(2 * target.exp_for_difficulty(attacker.lvl))
                    target.save()
        if success1:
            target.delete()
            if not success2:
                attacker.gain_experience(2 * target.exp_for_difficulty(target.lvl))
                attacker.save()
        msg = ""
        if success1:
            if success2:
                msg = "{0} killed {1} but died by blood loss from hes wounds."
            else:
                msg = "{0} succesfully killed {1}."
        else:
            if success2:
                msg = "The tables got turned and {0} was killed whilst trying to kill {1}."
            else:
                msg = "The blade has been dodged, no blood sheds today."
        Parent.SendStreamMessage(self.format_message(msg, attacker.name, target.name))
        # resolve additional attacks
        for child in fight.children:
            if child is not reaction:
                assert child.action == self.ATTACK_ACTION
                defense = False
                if child.target_id == target.char_id and reaction is not None and reaction.action == self.DEFEND_ACTION:
                    defense = True
                # sorted on time of making, so attacker still lives, if target is dead, too bad, can't kill dead dudes
                if child.attacker.attack(child.target, defense_bonus=defense)[0]:
                    child.target.delete()
                    child.attacker.gain_experience(2 * target.exp_for_difficulty(child.target.lvl))
                    child.attacker.save()
                    if child.target_id == attacker.char_id:
                        msg = self.format_message("{0} got ambushed by {1} whilst walking away from the fight",
                                                  attacker.name, child.attacker.name)
                    elif child.target_id == target.char_id:
                        msg = self.format_message("{0} got ambushed by {1} whilst walking away from the fight",
                                                  target.name, child.attacker.name)
                    else:
                        msg = self.format_message("{0} got assassinated by {1} whilst watching the fight",
                                                  child.target.name, child.attacker.name)
                    Parent.SendStreamMessage(msg)
        fight.delete()

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
            if location is None:
                Parent.SendStreamMessage(self.format_message(
                    "{0} the location {1} does not exists",
                    username,
                    location_name
                ))
            if character.location_id != location.id:
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
                conn.commit()
            else:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you are already in that location",
                    username
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
                fight = Attack.find_by_attacker_or_target(target, conn)
                attacker.exp_gain_time += dt.timedelta(seconds=self.scriptSettings.fight_resolve_time)
                attacker.save()
                if fight is None:
                    resolve_time = dt.datetime.now(utc) + dt.timedelta(seconds=self.scriptSettings.fight_resolve_time)
                    Attack.create(self.ATTACK_ACTION, attacker.char_id, target.char_id, resolve_time, connection=conn)
                    if target.exp_gain_time < resolve_time:
                        # TODO: solve https://stackoverflow.com/questions/9217411/python-datetimes-in-sqlite3
                        target.exp_gain_time = resolve_time
                        target.save()
                    if attacker.exp_gain_time < resolve_time:
                        attacker.exp_gain_time = resolve_time
                        attacker.save()
                else:
                    if fight.target_id == attacker.char_id:
                        resolver_id = fight.attack_id
                        Attack.create(self.COUNTER_ACTION, attacker.char_id, target.char_id, resolver_id=resolver_id,
                                      connection=conn)
                    else:
                        if fight.resolver_id is None:
                            resolver = fight
                        else:
                            resolver = Attack.find(fight.resolver_id)
                        Attack.create(self.ATTACK_ACTION, attacker.char_id, target.char_id, resolver_id=resolver.attack_id,
                                      connection=conn)
                        if attacker.exp_gain_time < resolver.resolve_time:
                            attacker.exp_gain_time = resolver.resolve_time
                            attacker.save()

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
