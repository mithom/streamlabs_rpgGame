from StaticData import Location, Weapon, Armor, Map
from characters import Character, Trait
from Attack import Attack
from Bounty import Bounty
import operator

import os
import datetime as dt
from pytz import utc


import clr

clr.AddReference("IronPython.SQLite.dll")
import sqlite3

Parent = None

LEFT = ["left", "east"]
RIGHT = ["right", "west"]
UP = ["up", "north"]
DOWN = ["down", "south"]


def get_coords_change(orientation):
    if orientation in LEFT:
        return -1, 0
    if orientation in RIGHT:
        return 1, 0
    if orientation in UP:
        return 0, 1
    if orientation in DOWN:
        return 0, -1
    assert False


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
        Map.get_map()  # init map variables

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
            Bounty.create_table_if_not_exists(conn)

    def create_and_load_static_data(self):
        with self.get_connection() as conn:
            Location.create_locations(conn)
            Location.load_locations(conn)
            Armor.create_armors(conn)
            Armor.load_armors(conn)
            Weapon.create_weapons(conn)
            Weapon.load_weapons(conn)
            Trait.create_traits(self.scriptSettings, conn)
            Character.load_static_data(conn)
            conn.commit()

    def apply_reload(self):
        pass

    def tick(self):
        with self.get_connection() as conn:
            # TODO: check if thread increases efficiency or not for small amounts of fights
            for fight in Attack.find_fights(conn):
                self.resolve_fight(fight, conn)
            lvl_up = []
            deaths = []
            characters = Character.find_by_past_exp_time(conn)
            coin_rewards = {}
            for character in characters:
                # TODO: almost certainly add paging + threading/page to support crowds.
                if character.check_survival():
                    coin_rewards[character.user_id] = character.position.location.difficulty
                    character.exp_gain_time = dt.datetime.now(utc) + dt.timedelta(
                        seconds=self.scriptSettings.xp_farm_time)
                    if character.gain_experience(character.exp_for_difficulty(character.position.location.difficulty)):
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

    def resolve_fight(self, fight, conn):
        kills = {}
        defenders = [attack.attacker_id for attack in fight.children if attack.action == self.DEFEND_ACTION]
        for attack in filter(lambda x: x.action == self.FLEE_ACTION, fight.children):
            if attack.attacker.attempt_flee():
                Parent.SendStreamMessage(self.format_message(
                    "{0} has successfully fled from the fight",
                    attack.attacker.name
                ))
        result = self.resolve_attack(fight, kills, defenders)
        if result is not None:
            kills.update(result)
        for attack in fight.children:
            result = self.resolve_attack(attack, kills, defenders)
            if result is not None:
                kills.update(result)
        fight.delete()
        for dead, killer in kills.iteritems():
            dead_char = Character.find(dead, conn)
            killer_char = Character.find(killer, conn)
            Parent.SendStreamMessage(self.format_message(
                "{0} has been killed by {1} and died at lvl {2}",
                dead_char.name,
                killer_char.name,
                dead_char.lvl
            ))
            if killer not in kills:
                killer_char.gain_experience(2 * killer_char.exp_for_difficulty(dead_char.lvl))
                killer_char.add_kill()
                self.pay_bounties(Bounty.find_all_by_character(dead, conn), killer_char.user_id)
                killer_char.save()
            dead_char.delete()

    def resolve_attack(self, fight, kills, defenders):
        attacker = fight.attacker
        target = fight.target
        if (attacker.char_id in kills and fight.action != self.COUNTER_ACTION) or \
                target is None or target.char_id in kills or attacker.position != target.position:
            return None
        if attacker.attack(target, defense_bonus=attacker.char_id in defenders,
                           attack_bonus=fight.action == self.COUNTER_ACTION):
            return {target.char_id: attacker.char_id}
        else:
            return None

    def pay_bounties(self, bounties, killer_user_id):
        to_pay = 0
        for bounty in bounties:
            to_pay += bounty.reward
            bounty.delete()
        if to_pay > 0:
            Parent.AddPoints(killer_user_id, Parent.GetDisplayName(killer_user_id), to_pay)
            if to_pay > 1000:  # TODO: setting for min_announcement_amount
                Parent.SendStreamMessage(self.format_message(
                    "{0} has claimed a huge amount of {1} in bounties!",
                    Parent.GetDisplayName(killer_user_id),
                    to_pay
                ))

    def commands(self):
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
            location = character.position.location
            Parent.SendStreamMessage(self.format_message(
                "{0}, your character {1} is located at {8}, which is a {2} with difficulty {3}. Your current lvl is {4} and xp {5}. " +
                "Your current are currently wearing {6} and use {7} as weapon",
                username,
                character.name,
                location.name,
                location.difficulty,
                character.lvl,
                character.experience,
                getattr(character.armor, "name", "rags"),
                getattr(character.weapon, "name", "bare hands"),
                str(character.position.coord)
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
                character.position.location.name,
                character.lvl
            ))

    def create(self, user_id, username, character_name):
        with self.get_connection() as conn:
            if Character.find_by_user(user_id, conn) is None and Character.find_by_name(character_name, conn) is None:
                exp_gain_time = dt.datetime.now(utc) + dt.timedelta(seconds=self.scriptSettings.xp_farm_time)
                x, y = Map.starting_position()
                Character.create(character_name, user_id, 0, 1, None, None, exp_gain_time, x, y, conn)
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

    def move(self, user_id, username, direction):
        with self.get_connection() as conn:
            if direction not in LEFT + RIGHT + UP + DOWN:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, that is no valid direction",
                    username
                ))
            character = Character.find_by_user(user_id, conn)
            if character is None:
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
                return
            if character.position.can_move_to(*get_coords_change(direction)):
                fight = Attack.find_by_attacker_or_target(character, conn)
                if fight is None:
                    character.position.coord = tuple(map(operator.add, character.position.coord, get_coords_change(direction)))
                    character.exp_gain_time = dt.datetime.now(utc) +\
                                              dt.timedelta(seconds=self.scriptSettings.xp_farm_time)
                    character.save()
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, {1} moved to location {2} with difficulty {3}",
                        username,
                        character.name,
                        character.position.location.name,
                        character.position.location.difficulty
                    ))
                else:
                    if fight.attacker_id == character.char_id:
                        Parent.SendStreamMessage(self.format_message(
                            "{0}, you cannot move during a fight, your action for this fight has already been set.",
                            username
                        ))
                    else:
                        Attack.create(self.FLEE_ACTION, character.char_id, resolver_id=fight.resolver_id,
                                      connection=conn)
                        Parent.SendStreamMessage(self.format_message(
                            "{0}, you cannot move during a fight, a flee attempt will be made.",
                            username
                        ))

            else:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, there is no location on that side",
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
                    if character.lvl >= armor.min_lvl and Parent.RemovePoints(user_id, username, armor.price):
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
            if target.position == attacker.position:
                fight = Attack.find_by_attacker_or_target(target, conn)
                if fight is None:
                    # delay xp time for attacker
                    attacker.exp_gain_time += dt.timedelta(seconds=self.scriptSettings.fight_resolve_time)
                    attacker.save()

                    # delay xp time for target
                    target.exp_gain_time += dt.timedelta(seconds=self.scriptSettings.fight_resolve_time)
                    target.save()

                    resolve_time = dt.datetime.now(utc) + dt.timedelta(seconds=self.scriptSettings.fight_resolve_time)
                    Attack.create(self.ATTACK_ACTION, attacker.char_id, target.char_id, resolve_time, connection=conn)
                else:
                    if fight.target_id == attacker.char_id:
                        # my xp has already been delayed, i just react only now
                        resolver_id = fight.resolver_id
                        Attack.create(self.COUNTER_ACTION, attacker.char_id, target.char_id, resolver_id=resolver_id,
                                      connection=conn)
                    else:
                        attacker.exp_gain_time += dt.timedelta(seconds=self.scriptSettings.fight_resolve_time)
                        attacker.save()

                        Attack.create(self.ATTACK_ACTION, attacker.char_id, target.char_id,
                                      resolver_id=fight.resolver_id, connection=conn)
            else:
                Parent.SendStreamMessage(
                    self.format_message("{0}, your target is not in the same area is you are.", username))
                return

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
                Attack.create(self.DEFEND_ACTION, defender.char_id, resolver_id=fight.resolver_id, connection=conn)

    def counter(self, user_id, username):
        with self.get_connection() as conn:
            countermen = Character.find_by_user(user_id, conn)
            if countermen is None:
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
                return
            fight = Attack.find_by_target(countermen, conn)
            if fight is None:
                Parent.SendStreamMessage("you are currently not being attacked")
                return
            else:
                Attack.create(self.COUNTER_ACTION, countermen.char_id, resolver_id=fight.resolver_id, connection=conn)

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
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you are currently not being attacked",
                    username
                ))
                return
            else:
                Attack.create(self.FLEE_ACTION, flee_char.char_id, resolver_id=fight.resolver_id, connection=conn)

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
        with self.get_connection() as conn:
            if recipient_name == self.scriptSettings.piebank_name:
                if Parent.RemovePoints(user_id, username, amount):
                    bounty = Bounty.find_by_user_id_from_piebank(user_id, conn)
                    if amount > 2 * bounty.reward:
                        bounty.delete()
                        Parent.SendStreamMessage(self.format_message(
                            "{0}, Your bounty has been cleared",
                            username
                        ))
                else:
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

    def bounty(self, user_id, username, target_name, amount):
        amount = int(amount)
        with self.get_connection() as conn:
            benefactor = Character.find_by_user(user_id, conn)
            if benefactor is None:
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet, username, self.scriptSettings.create_command
                ))
                return
            bounty = Bounty.find_by_character_name_and_benefactor(target_name, benefactor.char_id, conn)
            if bounty is None:
                target = Character.find_by_name(target_name, conn)
                if target is None:
                    Parent.SendStreamMessage(
                        self.format_message("{0}, no target exists with that character name", username))
                    return
                if Parent.RemovePoints(user_id, username, amount):
                    Bounty.create(target, benefactor, amount, None, conn)
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, bounty on {1} has been created for {2}",
                        username, target_name, amount
                    ))
            else:
                if bounty.reward >= amount:
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, your current bounty for {1} is larger then your new offer: {2}",
                        username, target_name, bounty.reward
                    ))
                else:
                    if Parent.RemovePoints(user_id, username, amount - bounty.reward):
                        bounty.reward = amount
                        bounty.save()
                        Parent.SendStreamMessage(self.format_message(
                            "{0}, your bounty on {1} has been updated",
                            username, target_name
                        ))

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
