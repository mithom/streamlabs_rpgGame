from StaticData import Location, Weapon, Armor, Map
from characters import Character, Trait
from Attack import Attack
from Bounty import Bounty
from Boss import Boss
from King import King, Tournament
import operator
import random
from Special import SpecialCooldown, Special, ActiveEffect, Item
from threading import Lock
from math import ceil
from functools import wraps

import os
import datetime as dt
from pytz import utc

import clr

clr.AddReference("IronPython.SQLite.dll")
import sqlite3

Parent = None
random = random.WichmannHill()


#  TODO: bosses billboard, view persons on same tile
#  TODO: attack cooldown, reset on being attacked (care to not reset on reaction)


def parse_datetime(adt):
    return adt.isoformat()


def convert_aware_timestamp(val):
    """this is adjusted from sqlite3/dbapi2.py convert_timestamp"""
    datepart, timepart = val.split("T")
    year, month, day = map(int, datepart.split("-"))
    timepart_full = timepart.split(".")
    if len(timepart_full) == 2:
        hours, minutes, seconds = map(int, timepart_full[0].split(":"))
        microseconds = int('{:0<6.6}'.format(timepart_full[1].decode()))
    else:
        hours, minutes, seconds = map(int, timepart.split("+")[0].split(":"))
        microseconds = 0

    val = dt.datetime(year, month, day, hours, minutes, seconds, microseconds)
    return utc.localize(val)


sqlite3.register_adapter(dt.datetime, parse_datetime)
sqlite3.register_converter("timestamp", convert_aware_timestamp)

LEFT = ["left", "west"]
RIGHT = ["right", "east"]
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


def connect(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            with args[0].get_connection() as conn:
                return f(*args, conn=conn, **kwargs)
        finally:
            Character.cache = {}
            if 'conn' in locals():
                # noinspection PyUnboundLocalVariable
                conn.close()
            args[0].db_lock.release()

    return wrapper


# noinspection PyUnboundLocalVariable,PyUnusedLocal
class RpgGame(object):
    db_lock = Lock()

    def __init__(self, script_settings, script_name, db_directory):
        self.scriptSettings = script_settings
        self.script_name = script_name
        self.db_directory = db_directory

        SpecialCooldown.Parent = Parent
        SpecialCooldown.format_message = self.format_message
        SpecialCooldown.max_steal_amount = script_settings.max_steal_amount

        # Pass on Parent object
        Character.Parent = Parent
        Character.format_message = self.format_message
        Character.game = self
        Attack.Parent = Parent
        Attack.format_message = self.format_message
        Attack.game = self

        # Prepare everything
        self.prepare_database()
        self.create_and_load_static_data()

        Map.get_map()  # init map variables

    def get_connection(self):
        if self.db_lock.acquire():
            return sqlite3.connect(os.path.join(self.db_directory, "database.db"), detect_types=sqlite3.PARSE_DECLTYPES)
        else:
            Parent.Log(self.script_name, 'could not acquire db lock in time (5s)')

    def prepare_database(self):
        with self.get_connection() as conn:
            # create all tables, location first, because character got foreign key to this
            Location.create_table_if_not_exists(conn)
            Weapon.create_table_if_not_exists(conn)
            Armor.create_table_if_not_exists(conn)
            Character.create_table_if_not_exists(conn)
            Item.create_table_if_not_exists(conn)
            Attack.create_table_if_not_exists(conn)
            Bounty.create_table_if_not_exists(conn)
            Boss.create_table_if_not_exists(conn)
            King.create_table_if_not_exists(conn)
            Tournament.create_table_if_not_exists(conn)
        conn.close()
        self.db_lock.release()

    def create_and_load_static_data(self):
        with self.get_connection() as conn:
            Location.create_locations(conn)
            Location.load_locations(conn)
            Armor.create_armors(conn)
            Armor.load_armors(conn)
            Weapon.create_weapons(conn)
            Weapon.load_weapons(conn)
            Trait.create_or_update_traits(self.scriptSettings, conn)
            Special.create_or_update_specials(self.scriptSettings, conn)
            Item.create_or_update_items(self.scriptSettings, conn)
            Item.load_items(self.scriptSettings, conn)
            Character.load_static_data(self.scriptSettings, conn)
            Boss.create_bosses(conn)
        conn.close()
        self.db_lock.release()

    def apply_reload(self):
        with self.get_connection() as conn:
            SpecialCooldown.max_steal_amount = self.scriptSettings.max_steal_amount
            Character.reload_static_data(self.scriptSettings, conn)
        conn.close()
        self.db_lock.release()

    def reset_db(self):
        self.db_lock.acquire()
        os.remove(os.path.join(self.db_directory, "database.db"))
        self.db_lock.release()
        Parent.Log(self.script_name, 'reset successful')

    @connect
    def tick(self, conn):
        king = King.find(conn)
        tournament = Tournament.find(conn)
        if tournament is None and self.scriptSettings.auto_contest:
            if king is None or king.character is None:
                participant_chars = Tournament.initiate_tournament(
                    king, max(self.scriptSettings.min_fight_lvl, 5), self.scriptSettings.max_participants, conn)
                if participant_chars is not None:
                    msg = "a tournament to become king has started between the top warriors: "
                    for part_char in participant_chars:
                        msg += part_char.name + ", "
                    Parent.SendStreamMessage(self.format_message(
                        msg[:-2]
                    ))
        else:
            winner = tournament.check_winner()
            if winner is not None:
                king = King.crown(winner, conn)
                tournament.delete()
                Parent.SendStreamMessage(self.format_message(
                    "{0} has proven worthy of the crown and shall become king/queen",
                    king.character.name
                ))
        Boss.respawn_bosses(conn)
        ActiveEffect.delete_all_expired(conn)
        self.do_boss_attacks(conn)
        for attack in Attack.find_boss_attack_past_resolve_time(conn):
            attack.resolve_boss_attack()
        for fight in Attack.find_fights(conn):
            fight.resolve_fight()
        lvl_up = []
        deaths = []
        characters = Character.find_by_past_exp_time(conn)
        coin_rewards = {}
        tax = 0
        if king is not None and king.character is not None:
            tax = king.tax_rate
            if tax != 0:
                coin_rewards[king.character.user_id] = 0
        for character in characters:
            if character.check_survival():
                coin_rewards[
                    character.user_id] = round(
                    character.position.location.reward * character.trait.loot_factor * (1 - tax / 100.0))
                if tax != 0:
                    coin_rewards[king.character.user_id] += round(character.position.location.reward *
                                                                  character.trait.loot_factor * (tax / 100.0))
                character.exp_gain_time = dt.datetime.now(utc) + dt.timedelta(
                    seconds=self.scriptSettings.xp_farm_time)
                if character.gain_experience(
                        character.exp_for_difficulty(character.position.location.difficulty)):
                    lvl_up.append(character)
                character.save()
            elif character.die():
                deaths.append(character)
        if len(coin_rewards) > 0:
            Parent.AddPointsAll(coin_rewards)
        conn.commit()
        if len(lvl_up) > 0:
            Parent.SendStreamMessage(self.format_message(
                "some characters just lvl'ed up: " + ", ".join(map(lambda char: char.name, lvl_up))
            ))
        if len(deaths) > 0:
            msg = ", ".join(map(lambda char: char.name + " got killed by a " +
                                             random.choice(char.position.location.monsters.split(",")) +
                                             " at lvl " + str(char.lvl), deaths))
            Parent.SendStreamMessage(self.format_message(msg))

    def do_boss_attacks(self, conn):
        for boss in Boss.find_by_active_and_past_attack_time(conn):
            killed_char = boss.do_attack(self.scriptSettings.fight_resolve_time)
            if killed_char is not None and killed_char.die():
                Parent.SendStreamMessage(self.format_message(
                    "{0}, {1} has been killed by boss {2}",
                    Parent.GetDisplayName(killed_char.user_id),
                    killed_char.name,
                    boss.name
                ))
            boss.save()

    def pay_bounties(self, bounties, killer_user_id):
        to_pay = 0
        for bounty in bounties:
            to_pay += bounty.reward
            bounty.delete()
        if to_pay > 0:
            Parent.AddPoints(killer_user_id, Parent.GetDisplayName(killer_user_id), to_pay)
            if to_pay > 1000:
                Parent.SendStreamMessage(self.format_message(
                    "{0} has claimed the huge amount of {1} in bounties!",
                    Parent.GetDisplayName(killer_user_id),
                    to_pay
                ))

    def commands(self):
        return [{
            self.scriptSettings.info_command: self.info,
            self.scriptSettings.condensed_info_command: self.condensed_info,
            self.scriptSettings.defend_command: self.defend,
            self.scriptSettings.counter_command: self.counter,
            self.scriptSettings.flee_command: self.flee,
            self.scriptSettings.dough_command: self.dough,
            self.scriptSettings.queen_command: self.queen,
            self.scriptSettings.king_command: self.king,
            self.scriptSettings.contest_command: self.contest,
            self.scriptSettings.tax_command: self.tax,
            "!" + self.scriptSettings.guardian_name: self.guardian,
            "!" + self.scriptSettings.empower_name: self.empower,
            "!" + self.scriptSettings.repel_name: self.repel,
            "!" + self.scriptSettings.invis_name: self.invis,
            self.scriptSettings.bounties_command: self.bounties,
            self.scriptSettings.topkills_command: self.top_kills,
            "!armors": self.armors,
            "!weapons": self.weapons,
            "!consumables": self.consumables,
        }, {
            self.scriptSettings.create_command: self.create,
            self.scriptSettings.move_command: self.move,
            self.scriptSettings.buy_command: self.buy,
            self.scriptSettings.attack_command: self.attack,
            self.scriptSettings.look_command: self.look,
            self.scriptSettings.tax_command: self.tax,
            self.scriptSettings.smite_command: self.smite,
            self.scriptSettings.unsmite_command: self.unsmite,
            "!" + self.scriptSettings.stun_name: self.stun,
            "!" + self.scriptSettings.track_name: self.track,
            "!" + self.scriptSettings.blind_name: self.blind,
            "!" + self.scriptSettings.curse_name: self.curse,
            "!" + self.scriptSettings.steal_name: self.steal,
            "!" + self.scriptSettings.guardian_name: self.guardian,
            "!" + self.scriptSettings.empower_name: self.empower,
            "!" + self.scriptSettings.repel_name: self.repel,
            "!" + self.scriptSettings.invis_name: self.invis,
            self.scriptSettings.bounties_command: self.bounties,
            self.scriptSettings.topkills_command: self.top_kills,
            self.scriptSettings.tp_command: self.teleport,
            "!armors": self.armors,
            "!weapons": self.weapons,
            "!consumables": self.consumables,
        }, {
            self.scriptSettings.give_command: self.give,
            self.scriptSettings.bounty_command: self.bounty,
        }]

    @connect
    def info(self, user_id, username, conn):
        character = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(character, username, stun_check=False):
            return
        location = character.position.location

        effects = ActiveEffect.find_all_by_target(character, conn)
        msg = "{username}, your character {char_name} is located at {coords}, which is a {loc_name} with " + \
              "difficulty {difficulty}. Your current lvl is {lvl} and xp {xp}/{needed_xp}. " + \
              "You are currently wearing {armor} and use {weapon} as weapon." + \
              " Your trait is {trait_name} with strength {trait_strength}"
        if len(character.specials) > 0:
            msg += " and specials: {specials}"
        if len(effects) > 0:
            msg += ", and are under the effects of: {effects}"

        Parent.SendStreamWhisper(user_id, self.format_message(
            msg,
            whisper=True,
            username=username,
            char_name=character.name,
            loc_name=location.name,
            difficulty=location.difficulty,
            lvl=character.lvl,
            xp=character.experience,
            needed_xp=character.exp_for_next_lvl(),
            weapon=getattr(character.weapon, "name", "bare hands"),
            armor=getattr(character.armor, "name", "rags"),
            coords=str(character.position.coord),
            trait_name=character.trait.trait.name,
            trait_strength=character.trait.strength or 0,
            specials=", ".join(map(lambda x: x.special.name, character.specials)),
            effects=", ".join(map(lambda x: x.usable.name + " for " +
                                            str((x.expiration_time - dt.datetime.now(utc)).total_seconds()) + "s",
                                  effects))
        ))

    @connect
    def condensed_info(self, user_id, username, conn):
        character = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(character, username, stun_check=False):
            return
        effects = ActiveEffect.find_all_by_target(character, conn)
        msg = "{0}, name: {1}, location {2}, lvl: {3}, trait: {4}, specials: {5}"
        if len(effects) > 0:
            msg += ", effects: {6}"
        Parent.SendStreamWhisper(user_id, self.format_message(
            msg,
            username,
            character.name,
            character.position.location.name,
            character.lvl,
            character.trait.trait.name,
            ", ".join(map(lambda x: x.special.identifier, character.specials)),
            ", ".join(map(lambda x: x.usable.identifier + ": " + str(x.expiration_time - dt.datetime.now(utc))[2:7],
                          effects)),
            whisper=True
        ))

    @connect
    def create(self, user_id, username, character_name, conn):
        if not Parent.HasPermission(user_id, self.scriptSettings.create_permission,
                                    self.scriptSettings.create_permission_info):
            Parent.SendStreamMessage(self.format_message(
                "{0}, the minimum rank for this command is {1}, {2}",
                username,
                self.scriptSettings.create_permission,
                self.scriptSettings.create_permission_info
            ))
            return
        if Character.find_by_user(user_id, conn) is None:
            if Character.find_by_name(character_name, conn) is None and \
                    Boss.find_by_name(character_name, conn) is None and \
                    Character.find_by_dead_and_name(character_name, conn) is None:
                exp_gain_time = dt.datetime.now(utc) + dt.timedelta(seconds=self.scriptSettings.xp_farm_time)
                x, y = Map.starting_position()
                old = Character.find_by_dead_and_user(user_id, conn)
                if old is not None:
                    specials = [sp.special.id for sp in old.specials]
                    effects = ActiveEffect.find_all_by_target(old, conn)
                    old.delete()
                new = Character.create(character_name, user_id, 0, 1, None, None, exp_gain_time, x, y, conn)
                if old is not None and Special.Specials.PERSIST in specials:
                    for special in specials:
                        if special != Special.Specials.PERSIST:
                            SpecialCooldown.create(new, special, connection=conn)
                    for effect in effects:
                        if effect.expiration_time is None:
                            ActiveEffect.create(new, effect.usable, conn)
                    new.armor = old.armor
                    new.weapon = old.weapon
                    new.save()
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you just created a new hero who listens to the mighty name of {1}. For more info about" +
                    " this hero, type " + self.scriptSettings.info_command,
                    username,
                    character_name
                ))
            else:
                Parent.SendStreamWhisper(user_id, self.format_message(
                    "{0}, character could not be created, {1} is already taken, or still being mourned",
                    username,
                    character_name,
                    whisper=True
                ))
        else:
            Parent.SendStreamWhisper(user_id, self.format_message(
                "{0}, character could not be created, already have a character. !info to know everything about hem.",
                username,
                whisper=True
            ))

    @connect
    def move(self, user_id, username, direction, conn):
        if Parent.IsOnUserCooldown(self.script_name, 'move', user_id):
            Parent.SendStreamMessage(self.format_message(
                '{0}, you cannot move for ' +
                str(Parent.GetUserCooldownDuration(self.script_name, 'move', user_id)) + ' seconds.',
                username
            ))
            return
        if direction not in LEFT + RIGHT + UP + DOWN:
            Parent.AddUserCooldown(self.script_name, 'move', user_id, self.scriptSettings.xp_farm_time / 5)
            Parent.SendStreamMessage(self.format_message(
                "{0}, that is no valid direction",
                username
            ))
            return
        character = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(character, username):
            Parent.AddUserCooldown(self.script_name, 'move', user_id, self.scriptSettings.xp_farm_time / 5)
            return
        if character.position.can_move_to(*get_coords_change(direction)):
            fight = Attack.find_by_attacker_or_target(character, conn)
            if fight is None:
                if not character.is_stunned():
                    character.position.coord = tuple(
                        map(operator.add, character.position.coord, get_coords_change(direction)))
                    character.exp_gain_time = dt.datetime.now(utc) + \
                                              dt.timedelta(seconds=self.scriptSettings.xp_farm_time)
                    character.save()
                    Parent.AddUserCooldown(self.script_name, 'move', user_id, self.scriptSettings.xp_farm_time)
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, {1} moved to location {2} with difficulty {3}",
                        username,
                        character.name,
                        character.position.location.name,
                        character.position.location.difficulty
                    ))
                else:
                    Parent.AddUserCooldown(self.script_name, 'move', user_id,
                                           self.scriptSettings.xp_farm_time / 5)
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, you cannot move while stunned!",
                        username
                    ))
            else:
                Parent.AddUserCooldown(self.script_name, 'move', user_id, self.scriptSettings.xp_farm_time / 5)
                if fight.attacker_id == character.char_id:
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, you cannot move during a fight, your action for this fight has already been set.",
                        username
                    ))
                else:
                    Attack.create(Attack.FLEE_ACTION, character.char_id, resolver_id=fight.resolver_id,
                                  connection=conn)
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, you cannot move during a fight, a flee attempt will be made.",
                        username
                    ))

        else:
            Parent.AddUserCooldown(self.script_name, 'move', user_id, self.scriptSettings.xp_farm_time / 5)
            Parent.SendStreamMessage(self.format_message(
                "{0}, there is no location on that side",
                username
            ))

    @connect
    def buy(self, user_id, username, item_name, conn):
        character = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(character, username):
            return
        weapon = Weapon.find_by_name(item_name)
        if weapon is not None:
            if character.lvl >= weapon.min_lvl and Parent.RemovePoints(user_id, username, weapon.price):
                character.weapon = weapon
                character.save()
                Parent.SendStreamMessage(self.format_message(
                    "{0}, {1} successfully bought {2}",
                    username, character.name, weapon.name
                ))
            else:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, {1} failed to buy {2}",
                    username, character.name, weapon.name
                ))
        else:
            armor = Armor.find_by_name(item_name)
            if armor is not None:
                if character.lvl >= armor.min_lvl and Parent.RemovePoints(user_id, username, armor.price):
                    character.armor = armor
                    character.save()
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, {1} successfully bought {2}",
                        username, character.name, armor.name
                    ))
                else:
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, {1} failed to buy {2}",
                        username, character.name, armor.name
                    ))
            else:
                item = Item.find_by_name(item_name)
                if item is not None:
                    if character.lvl >= item.min_lvl and item.can_buy(character) and \
                            Parent.RemovePoints(user_id, username, item.price):
                        item.use(character)
                else:
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, {1} does not exists",
                        username,
                        item_name
                    ))

    @connect
    def attack(self, user_id, username, target_name, conn):
        target = Character.find_by_name(target_name, conn)
        attacker = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(attacker, username):
            return
        if attacker.lvl < self.scriptSettings.min_fight_lvl:
            Parent.SendStreamMessage(self.format_message(
                "{0}, your character isn't lvl {lvl} yet",
                username, lvl=self.scriptSettings.min_fight_lvl
            ))
            return
        fight1 = Attack.find_by_attacker_or_target(attacker, conn)
        if target is None:
            boss = Boss.find_by_name(target_name, conn)
            if boss is None:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, no target exists with that character name",
                    username))
                return
            else:
                if fight1 is not None:
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, you are already in a fight, focus on that fight first!",
                        username
                    ))
                    return
                if boss.position != attacker.position:
                    Parent.SendStreamMessage(
                        self.format_message("{0}, your target is not in the same area is you are.", username))
                    return
                else:
                    if boss.state is Boss.State.DEAD:
                        Parent.SendStreamMessage(
                            self.format_message("{0}, this boss is currenlty dead. It will respawn in {1}",
                                                username, str(boss.respawn_time - dt.datetime.now(utc))))
                        return
                    else:
                        resolve_time = dt.datetime.now(utc) + dt.timedelta(
                            seconds=self.scriptSettings.fight_resolve_time)
                        attacker.remove_invisibility()
                        Attack.create(Attack.ATTACK_ACTION, attacker.char_id, boss_id=boss.boss_id,
                                      resolve_time=resolve_time, connection=conn)
                        Parent.SendStreamMessage(self.format_message(
                            "{0} starts clashing with the big boss {1}",
                            attacker.name,
                            boss.name
                        ))
                        return
        elif target.is_invisible():
            Parent.SendStreamMessage(self.format_message(
                "{0}, you cannot find {1}!",
                username,
                target.name
            ))
            return
        elif target.position == attacker.position:
            if attacker.position.location.difficulty == 0:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, the castle is a peaceful place!",
                    username
                ))
                return
            if target.lvl < self.scriptSettings.min_fight_lvl:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, {target} isn't lvl {lvl} yet",
                    username, lvl=self.scriptSettings.min_fight_lvl, target=target_name
                ))
                return
            if fight1 is not None:
                if fight1.attacker_id == attacker.char_id:
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, you are already attacking someone", username
                    ))
                    return
                if fight1.attacker_id != target.char_id:
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, you are being attacked by {1}, you should fight hem first",
                        username,
                        target.name
                    ))
                    return
            fight = Attack.find_by_attacker_or_target(target, conn)
            if fight is None:
                if attacker.participate_in_same_tournament(target):
                    # delay xp time for attacker
                    attacker.exp_gain_time += dt.timedelta(seconds=self.scriptSettings.fight_resolve_time)
                    attacker.save()

                    # delay xp time for target
                    target.exp_gain_time += dt.timedelta(seconds=self.scriptSettings.fight_resolve_time)
                    target.save()

                    resolve_time = dt.datetime.now(utc) + \
                                   dt.timedelta(seconds=self.scriptSettings.fight_resolve_time)
                    attacker.remove_invisibility()
                    Attack.create(Attack.ATTACK_ACTION, attacker.char_id, target.char_id, resolve_time,
                                  connection=conn)
                    Parent.SendStreamMessage(self.format_message(
                        "{0} challenges {1} to a fight",
                        attacker.name, target.name
                    ))
                else:
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, you can not attack {1} as you are not in the same tournament.",
                        username,
                        target.name
                    ))
                    return
            else:
                if fight.target_id == attacker.char_id:
                    # my xp has already been delayed, i just react only now
                    resolver_id = fight.resolver_id
                    Attack.create(Attack.COUNTER_ACTION, attacker.char_id, target.char_id,
                                  resolver_id=resolver_id, connection=conn)
                    Parent.SendStreamMessage(self.format_message(
                        "{0} accepts the challenge and prepares to counter {1}",
                        attacker.name, target.name
                    ))
                else:
                    attacker.exp_gain_time += dt.timedelta(seconds=self.scriptSettings.fight_resolve_time)
                    attacker.save()

                    Attack.create(Attack.ATTACK_ACTION, attacker.char_id, target.char_id,
                                  resolver_id=fight.resolver_id, connection=conn)
                    Parent.SendStreamMessage(self.format_message(
                        "{0} sees an opportunity to sneak up on {1}",
                        attacker.name, target.name
                    ))
        else:
            Parent.SendStreamMessage(
                self.format_message("{0}, your target is not in the same area is you are.", username))
            return

    @connect
    def defend(self, user_id, username, conn):
        defender = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(defender, username):
            return
        fight = Attack.find_by_target(defender, conn)
        if fight is None:
            Parent.SendStreamMessage(self.format_message(
                "{0}, you are currently not being attacked",
                defender.name
            ))
            return
        else:
            Attack.create(Attack.DEFEND_ACTION, defender.char_id, resolver_id=fight.resolver_id,
                          connection=conn)
            Parent.SendStreamMessage(self.format_message(
                "{0} has taken a defensive pose",
                defender.name
            ))

    @connect
    def counter(self, user_id, username, conn):
        countermen = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(countermen, username):
            return
        fight = Attack.find_by_target(countermen, conn)
        if fight is None:
            Parent.SendStreamMessage(self.format_message(
                "{0}, you are currently not being attacked",
                countermen.name
            ))
            return
        else:
            Attack.create(Attack.COUNTER_ACTION, countermen.char_id, fight.attacker_id, resolver_id=fight.resolver_id,
                          connection=conn)
            Parent.SendStreamMessage(self.format_message(
                "{0} prepares to counter attack",
                countermen.name
            ))

    @connect
    def flee(self, user_id, username, conn):
        flee_char = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(flee_char, username):
            return
        fight = Attack.find_by_target(flee_char, conn)
        if fight is None:
            Parent.SendStreamMessage(self.format_message(
                "{0}, you are currently not being attacked",
                flee_char.name
            ))
            return
        else:
            Parent.SendStreamMessage(self.format_message(
                "{0} starts looking for a way out of this fight",
                flee_char.name
            ))
            Attack.create(Attack.FLEE_ACTION, flee_char.char_id, resolver_id=fight.resolver_id, connection=conn)

    @connect
    def look(self, _, username, target_name, conn):
        target_char = Character.find_by_name(target_name, conn)
        if not self.check_valid_target(target_char, username, target_name):
            return
        equipment_str = "badly equipped for hes lvl"

        equipment_lvl = 0
        if target_char.weapon is not None:
            equipment_lvl += target_char.weapon.min_lvl
        if target_char.armor is not None:
            equipment_lvl += target_char.armor.min_lvl

        if equipment_lvl >= target_char.lvl * 1.5:
            equipment_str = "greatly equipped for hes lvl "
        elif equipment_lvl >= target_char.lvl:
            equipment_str = "well equipped for hes lvl "

        Parent.SendStreamMessage(self.format_message(
            "{0}, {1} is currently lvl {2}. He looks {3}",
            username,
            target_name,
            target_char.lvl,
            equipment_str
        ))

    def dough(self, user_id, username):
        Parent.SendStreamMessage(self.format_message("{0}, your current piecoin balance is {1} {2}",
                                                     username,
                                                     Parent.GetPoints(user_id),
                                                     Parent.GetCurrencyName()
                                                     ))

    @connect
    def give(self, user_id, username, amount, recipient_name, conn):
        amount = int(amount)
        if recipient_name == self.scriptSettings.piebank_name:
            if Parent.RemovePoints(user_id, username, amount):
                bounty = Bounty.find_by_user_id_from_piebank(user_id, conn)
                if bounty is not None and amount >= 2 * bounty.reward and bounty.kill_count > 1:
                    bounty.delete()
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, Your bounty has been cleared",
                        username
                    ))
                else:
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, thanks for the kindness of this free donation",
                        username
                    ))
            else:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you don't have enough coins", username
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
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, something went wrong", username
                    ))
            else:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you don't have enough coins", username
                ))

    @connect
    def bounty(self, user_id, username, target_name, amount, conn):
        amount = int(amount)
        benefactor = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(benefactor, username, stun_check=False):
            return
        bounty = Bounty.find_by_character_name_and_benefactor(target_name, benefactor.char_id, conn)
        if bounty is None:
            target = Character.find_by_name(target_name, conn)
            if not self.check_valid_target(target, username, target_name, invisible_check=False):
                return
            if Parent.RemovePoints(user_id, username, amount):
                Bounty.create(target, benefactor, amount, None, conn)
                Parent.SendStreamMessage(self.format_message(
                    "{0}, bounty on {1} has been created for {2}",
                    username, target_name, amount
                ))
            else:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you don't have enough points to do that!",
                    username
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

    @connect
    def bounties(self, user_id, username, paging="1", conn=None):
        page = int(paging)
        pages = int(ceil(Bounty.count(conn) / 5.0))
        if pages == 0:
            Parent.SendStreamMessage(self.format_message(
                "there are no bounties currently"
            ))
        elif page > pages:
            Parent.SendStreamMessage(self.format_message(
                "there are currently only {0} pages",
                pages
            ))
        else:
            top = Bounty.find_all_ordered_by_worth(page, 5, conn)
            Parent.SendStreamMessage(self.format_message(
                "bounties: {0}, page {1}/{2}",
                ', '.join(map(lambda x: x.character.name + ": " + str(x.reward), top)),
                page,
                pages
            ))

    @connect
    def top_kills(self, user_id, username, paging="1", conn=None):
        page = int(paging)
        pages = int(ceil(Bounty.count(conn, True) / 5.0))
        if pages == 0:
            Parent.SendStreamMessage(self.format_message(
                "there are no killers currently"
            ))
        elif page > pages:
            Parent.SendStreamMessage(self.format_message(
                "there are currently only {0} pages",
                pages
            ))
        else:
            top = Bounty.find_all_ordered_by_kills(page, 5, conn)
            Parent.SendStreamMessage(self.format_message(
                "kills: {0}, page {1}/{2}",
                ', '.join(map(lambda x: x.character.name + ": " + str(x.kill_count), top)),
                page,
                pages
            ))

    def armors(self, user_id, username, paging="1", conn=None):
        page = int(paging)
        pages = int(ceil(len(Armor.data_by_id) / 5.0))
        if pages == 0:
            return
        if page > pages:
            if pages > 0:
                Parent.SendStreamMessage(self.format_message(
                    "there are currently only {0} pages",
                    pages
                ))
        else:
            data = sorted(Armor.data_by_id.values(), key=lambda x: x.min_lvl)
            Parent.SendStreamMessage(self.format_message(
                "armors: {0}, page {1}/{2}",
                ", ".join(map(lambda x: x.name + "[price: " + str(x.price) + ", lvl: " + str(x.min_lvl) + "]",
                              data[(page - 1) * 5:page * 5])),
                page,
                pages
            ))

    def weapons(self, user_id, username, paging="1", conn=None):
        page = int(paging)
        pages = int(ceil(len(Weapon.data_by_id) / 5.0))
        if pages == 0:
            return
        if page > pages:
            if pages > 0:
                Parent.SendStreamMessage(self.format_message(
                    "there are currently only {0} pages",
                    pages
                ))
        else:
            data = sorted(Weapon.data_by_id.values(), key=lambda x: x.min_lvl)
            Parent.SendStreamMessage(self.format_message(
                "weapons: {0}, page {1}/{2}",
                ", ".join(map(lambda x: x.name + "[price: " + str(x.price) + ", lvl: " + str(x.min_lvl) + "]",
                              data[(page - 1) * 5:page * 5])),
                page,
                pages
            ))

    def consumables(self, user_id, username, paging="1", conn=None):
        page = int(paging)
        pages = int(ceil(len(Item.data_by_id) / 5.0))
        if pages == 0:
            return
        if page > pages:
            if pages > 0:
                Parent.SendStreamMessage(self.format_message(
                    "there are currently only {0} pages",
                    pages
                ))
        else:
            data = sorted(Item.data_by_id.values(), key=lambda x: x.min_lvl)
            Parent.SendStreamMessage(self.format_message(
                "consumables: {0}, page {1}/{2}",
                ", ".join(map(lambda x: x.name + "[price: " + str(x.price) + ", lvl: " + str(x.min_lvl) + "]",
                              data[(page - 1) * 5:page * 5])),
                page,
                pages
            ))

    @connect
    def tax(self, user_id, username, amount=None, conn=None):
        king = King.find(conn)
        char = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(char, username, stun_check=False):
            return
        if char.char_id == king.character_id and amount is not None:
            amount = int(amount)
            king.tax_rate = max(min(amount, 10), 0)
            king.save()
        Parent.SendStreamMessage(self.format_message(
            "your {0} set the tax to {1}%",
            king.gender,
            king.tax_rate
        ))

    @connect
    def queen(self, user_id, username, conn):
        king = King.find(conn)
        char = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(char, username, stun_check=False):
            return
        if king is not None and king.character_id == char.char_id:
            king.gender = "queen"
            king.save()
            Parent.SendStreamMessage(self.format_message(
                "{0}, your title has been set to queen",
                char.name
            ))
        elif king is not None and king.character is not None:
            Parent.SendStreamMessage(self.format_message(
                "our current {0} is {1}",
                king.gender,
                king.character.name
            ))
        else:
            Parent.SendStreamMessage(self.format_message(
                "Pieland doesn't have a king or queen currently"
            ))

    @connect
    def king(self, user_id, username, conn):
        king = King.find(conn)
        char = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(char, username, stun_check=False):
            return
        if king is not None and king.character_id == char.char_id:
            king.gender = "king"
            king.save()
            Parent.SendStreamMessage(self.format_message(
                "{0}, your title has been set to king",
                char.name
            ))
        elif king is not None and king.character is not None:
            Parent.SendStreamMessage(self.format_message(
                "our current {0} is {1}",
                king.gender,
                king.character.name
            ))
        else:
            Parent.SendStreamMessage(self.format_message(
                "Pieland doesn't have a king or queen currently"
            ))

    @connect
    def contest(self, user_id, username, conn):
        char = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(char, username):
            return
        king = King.find(conn)
        tournament = Tournament.find(conn)
        if tournament is not None:
            Parent.SendStreamMessage(self.format_message(
                "{0}, a tournament to become king is already in progress",
                username
            ))
            return
        if king is not None and king.indisputable_until > dt.datetime.now(utc):
            delta = king.indisputable_until - dt.datetime.now(utc)
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            delta_str = '{:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds))
            Parent.SendStreamMessage(self.format_message(
                "{0} the {1} cannot be disputed so short after hes crowning, please wait {2}",
                username,
                king.gender,
                delta_str
            ))
            return
        candidates = Character.get_order_by_lvl_and_xp(3, conn, min_lvl=max(self.scriptSettings.min_fight_lvl, 5))
        if king.character_id not in map(lambda x: x.char_id, candidates):
            candidates = candidates[0:-1]
        if char not in candidates:
            Parent.SendStreamMessage(self.format_message(
                "{0}, you are not eligible to become king",
                char.name
            ))
            return
        participant_chars = Tournament.initiate_tournament(
            king, max(self.scriptSettings.min_fight_lvl, max(self.scriptSettings.min_fight_lvl, 5)),
            self.scriptSettings.max_participants, conn)
        if participant_chars is not None:
            msg = "a tournament to become king has started between the top warriors: "
            for part_char in participant_chars:
                msg += part_char.name + ", "
            Parent.SendStreamMessage(self.format_message(
                msg[:-2]
            ))
        else:
            Parent.SendStreamMessage(self.format_message(
                "{0}, at least 2 candidates needed to start a tournament",
                username
            ))

    def smite(self, user_id, username, target_name):
        pass

    def unsmite(self, user_id, username, target_name):
        pass

    @connect
    def teleport(self, user_id, username, tp_name, conn):
        char = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(char, username):
            return

        target_location = Map.tp_positions().get(tp_name, None)
        fight = Attack.find_by_attacker_or_target(char, conn)

        if target_location is None or target_location == char.position:
            Parent.SendStreamMessage(self.format_message(
                "{0}, you cannot teleport to that place",
                username
            ))
        elif fight is not None:
            Parent.SendStreamMessage(self.format_message(
                "{0}, you cannot teleport while in a fight", username
            ))
        else:  # general tp conditions have been met, now check specific case
            warp_tonic = ActiveEffect.find_by_target_and_special(char, Item.Items.WARP_TONIC, conn)
            is_on_user_cd = Parent.IsOnUserCooldown(self.script_name, "tp", user_id)
            if is_on_user_cd and warp_tonic is None:  # no only case applies
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you can't do that right now, pls wait {1} seconds.",
                    username,
                    Parent.GetUserCooldownDuration(self.script_name, 'tp', user_id)
                ))
            elif char.position in Map.tp_positions().itervalues() and not is_on_user_cd:
                Parent.AddUserCooldown(self.script_name, "tp", user_id, 600)
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you touch the portal and suddenly feel lightheaded as you start to disappear...",
                    username
                ))
                char.position.coord = target_location.coord
                char.save()
            elif warp_tonic is not None:
                warp_tonic.delete()
                char.position.coord = target_location.coord
                char.save()
                Parent.SendStreamMessage(self.format_message(
                    """{0}, you take a sip of the potion and fall asleep... you wake up at a new location""",
                    username
                ))
            else:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you need to be at a portal to teleport!",
                    username
                ))

    # ---------------------------------------
    #   specials functions
    # ---------------------------------------
    @connect
    def stun(self, user_id, username, target_name, conn):
        char = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(char, username):
            return
        target = Character.find_by_name(target_name, conn)
        if not self.check_valid_target(target, username, target_name):
            return
        char.use_special(Special.Specials.STUN, target)

    @connect
    def track(self, user_id, username, target_name, conn):
        char = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(char, username):
            return
        target = Character.find_by_name(target_name, conn)
        if not self.check_valid_target(target, username, target_name):
            return
        char.use_special(Special.Specials.TRACK, target)

    @connect
    def guardian(self, user_id, username, target_name=None, conn=None):
        char = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(char, username):
            return
        if target_name is None:
            target = char
        else:
            target = Character.find_by_name(target_name, conn)
            if not self.check_valid_target(target, username, target_name):
                return
        char.use_special(Special.Specials.GUARDIAN, target)

    @connect
    def empower(self, user_id, username, target_name=None, conn=None):
        char = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(char, username):
            return
        if target_name is None:
            target = char
        else:
            target = Character.find_by_name(target_name, conn)
            if not self.check_valid_target(target, username, target_name):
                return
        char.use_special(Special.Specials.EMPOWER, target)

    @connect
    def repel(self, user_id, username, target_name=None, conn=None):
        char = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(char, username, stun_check=False):
            return
        if target_name is None:
            target = char
        else:
            target = Character.find_by_name(target_name, conn)
            if not self.check_valid_target(target, username, target_name):
                return
        char.use_special(Special.Specials.REPEL, target)

    @connect
    def blind(self, user_id, username, target_name, conn):
        char = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(char, username):
            return
        target = Character.find_by_name(target_name, conn)
        if not self.check_valid_target(target, username, target_name):
            return
        char.use_special(Special.Specials.BLIND, target)

    @connect
    def curse(self, user_id, username, target_name, conn):
        char = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(char, username):
            return
        target = Character.find_by_name(target_name, conn)
        if not self.check_valid_target(target, username, target_name):
            return
        char.use_special(Special.Specials.CURSE, target)

    @connect
    def invis(self, user_id, username, target_name=None, conn=None):
        char = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(char, username):
            return
        if target_name is None:
            target = char
        else:
            target = Character.find_by_name(target_name, conn)
            if not self.check_valid_target(target, username, target_name):
                return
        char.use_special(Special.Specials.INVIS, target)

    @connect
    def steal(self, user_id, username, target_name, conn):
        char = Character.find_by_user(user_id, conn)
        if not self.check_valid_char(char, username):
            return
        target = Character.find_by_name(target_name, conn)
        if not self.check_valid_target(target, username, target_name):
            return
        char.use_special(Special.Specials.STEAL, target)

    # ---------------------------------------
    #   auxiliary functions
    # ---------------------------------------
    def format_message(self, msg, *args, **kwargs):
        if self.scriptSettings.add_me and not kwargs.get('whisper', False):
            msg = "/me " + msg
        return msg.format(*args, **kwargs)

    def check_valid_char(self, char, username, stun_check=True):
        if char is None:
            Parent.SendStreamMessage(self.format_message(
                self.scriptSettings.no_character_yet,
                username,
                self.scriptSettings.create_command
            ))
            return False
        if stun_check and char.is_stunned():
            Parent.SendStreamMessage(self.format_message(
                "{0}, you cannot do that while stunned!",
                char.name
            ))
            return False
        return True

    def check_valid_target(self, char, username, char_name, invisible_check=True):
        if char is None:
            Parent.SendStreamMessage(self.format_message(
                "{0}, there is no character called {1}",
                username,
                char_name
            ))
            return False
        if invisible_check and char.is_invisible():
            Parent.SendStreamMessage(self.format_message(
                "{0}, you cannot find {1}!",
                username,
                char.name
            ))
            return False
        return True
