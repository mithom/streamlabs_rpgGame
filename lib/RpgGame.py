from StaticData import Location, Weapon, Armor, Map
from characters import Character, Trait
from Attack import Attack
from Bounty import Bounty
from Boss import Boss
import operator
import random
from Special import SpecialCooldown, Special, ActiveEffect


import os
import datetime as dt
from pytz import utc

import clr

clr.AddReference("IronPython.SQLite.dll")
import sqlite3

Parent = None


def parse_datetime(adt):
    return adt.isoformat(" ")


def convert_aware_timestamp(val):
    """this is adjusted from sqlite3/dbapi2.py convert_timestamp"""
    datepart, timepart = val.split(" ")
    year, month, day = map(int, datepart.split("-"))
    timepart_full = timepart.split(".")
    hours, minutes, seconds = map(int, timepart_full[0].split(":"))
    if len(timepart_full) == 2:
        microseconds = int('{:0<6.6}'.format(timepart_full[1].decode()))
    else:
        microseconds = 0

    val = dt.datetime(year, month, day, hours, minutes, seconds, microseconds)
    return utc.localize(val)


sqlite3.register_adapter(dt.datetime, parse_datetime)
sqlite3.register_converter("timestamp", convert_aware_timestamp)

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

        SpecialCooldown.Parent = Parent
        SpecialCooldown.format_message = self.format_message
        SpecialCooldown.max_steal_amount = script_settings.max_steal_amount

        # Pass on Parent object
        Character.Parent = Parent
        Character.format_message = self.format_message

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
            Boss.create_table_if_not_exists(conn)
        conn.close()

    def create_and_load_static_data(self):
        with self.get_connection() as conn:
            Location.create_locations(conn)
            Location.load_locations(conn)
            Armor.create_armors(conn)
            Armor.load_armors(conn)
            Weapon.create_weapons(conn)
            Weapon.load_weapons(conn)
            Trait.create_traits(self.scriptSettings, conn)
            Special.create_specials(self.scriptSettings, conn)
            Character.load_static_data(conn)
            Boss.create_bosses(conn)
        conn.close()

    def apply_reload(self):
        SpecialCooldown.max_steal_amount = self.scriptSettings.max_steal_amount

    def tick(self):
        with self.get_connection() as conn:
            # TODO: check if thread increases efficiency or not for small amounts of fights
            Boss.respawn_bosses(conn)
            ActiveEffect.delete_all_expired(conn)
            self.do_boss_attacks(conn)
            for attack in Attack.find_boss_attack_past_resolve_time(conn):
                self.resolve_boss_attack(attack, conn)
            for fight in Attack.find_fights(conn):
                self.resolve_fight(fight, conn)
            lvl_up = []
            deaths = []
            characters = Character.find_by_past_exp_time(conn)
            coin_rewards = {}
            for character in characters:
                # TODO: almost certainly add paging + threading/page to support crowds.
                if character.check_survival():
                    coin_rewards[
                        character.user_id] = round(character.position.location.difficulty * character.trait.loot_factor)
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
        conn.close()

    def do_boss_attacks(self, conn):
        for boss in Boss.find_by_active_and_past_attack_time(conn):
            killed_char = boss.do_attack(self.scriptSettings.fight_resolve_time)
            if killed_char is not None:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, {1} has been killed by boss {2}",
                    Parent.GetDisplayName(killed_char.user_id),
                    killed_char.name,
                    boss.name
                ))
                killed_char.delete()
            boss.save()

    def resolve_boss_attack(self, attack, conn):
        boss = Boss.find(attack.boss_id, conn)
        if boss.state != boss.State.DEAD:
            if attack.attacker.attack_boss(boss):
                specials = set(Special.data_by_id.keys())
                character_specials = set(map(lambda x: x.specials_orig_name, attack.attacker.specials))
                new_specials = specials-character_specials
                if len(new_specials) > 0:
                    new_special_id = random.choice(list(new_specials))
                    special = SpecialCooldown.create(attack.attacker_id, new_special_id, conn)
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, {1} has gained the ability {2} ({3}) on a {4} seconds cooldown.",
                        Parent.GetDisplayName(attack.attacker.user_id),
                        attack.attacker.name,
                        special.special.name,
                        special.special.identifier,
                        special.special.cooldown_time
                    ))
                else:
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, your character {1} already has every available special and cannot get a new one.",
                        Parent.GetDisplayName(attack.attacker.user_id),
                        attack.attacker.name
                    ))
            boss.save()
        attack.delete()

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
            result = self.resolve_attack(attack, kills, defenders, sneak=True)
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

    def resolve_attack(self, fight, kills, defenders, sneak=False):
        attacker = fight.attacker
        target = fight.target
        sneak = sneak and self.COUNTER_ACTION != fight.action
        if (attacker.char_id in kills and fight.action != self.COUNTER_ACTION) or \
                target is None or target.char_id in kills or attacker.position != target.position:
            return None
        if attacker.attack(target, defense_bonus=attacker.char_id in defenders,
                           attack_bonus=fight.action == self.COUNTER_ACTION, sneak=sneak):
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
            self.scriptSettings.king_command: self.king,
            "!" + self.scriptSettings.guardian_name: self.guardian,
            "!" + self.scriptSettings.empower_name: self.empower,
            "!" + self.scriptSettings.repel_name: self.repel,
            "!" + self.scriptSettings.invis_name: self.invis,
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
            "!" + self.scriptSettings.stun_name: self.stun,
            "!" + self.scriptSettings.track_name: self.track,
            "!" + self.scriptSettings.blind_name: self.blind,
            "!" + self.scriptSettings.curse_name: self.curse,
            "!" + self.scriptSettings.steal_name: self.steal,
            "!" + self.scriptSettings.guardian_name: self.guardian,  # those last 4 can be both with or without target
            "!" + self.scriptSettings.empower_name: self.empower,
            "!" + self.scriptSettings.repel_name: self.repel,
            "!" + self.scriptSettings.invis_name: self.invis,
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
                "{username}, your character {char_name} is located at {coords}, which is a {loc_name} with difficulty" +
                " {difficulty}. Your current lvl is {lvl} and xp {xp}/{needed_xp}. " +
                "You are currently wearing {armor} and use {weapon} as weapon." +
                " Your trait is {trait_name} with strength {trait_strength} and specials: {specials}",
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
                specials=", ".join(map(lambda x: x.special.name, character.specials))
            ))
        conn.close()

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
                "{0}, name: {1}, location {2}, lvl: {3}, trait: {4} specials: {5}",
                username,
                character.name,
                character.position.location.name,
                character.lvl,
                character.trait.trait.name,
                ", ".join(map(lambda x: x.special.identifier, character.specials))
            ))
        conn.close()

    def create(self, user_id, username, character_name):
        with self.get_connection() as conn:
            if Character.find_by_user(user_id, conn) is None and\
                    Character.find_by_name(character_name, conn) is None and \
                    Boss.find_by_name(character_name, conn) is None:
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
        conn.close()

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
                    if not character.is_stunned():
                        character.position.coord = tuple(
                            map(operator.add, character.position.coord, get_coords_change(direction)))
                        character.exp_gain_time = dt.datetime.now(utc) + \
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
                        Parent.SendStreamMessage(self.format_message(
                            "{0}, you cannot move while stunned!",
                            username
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
        conn.close()

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
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, {1} does not exists",
                        username,
                        item_name
                    ))
        conn.close()

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
            if attacker.is_stunned():
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you cannot move while stunned!",
                    username
                ))
                return
            fight1 = Attack.find_by_attacker_or_target(attacker, conn)
            if fight1 is not None:
                if fight1.attacker_id == attacker.char_id:
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, you are already attacking someone", username
                    ))
                    return
            if target is None:
                boss = Boss.find_by_name(target_name, conn)
                if boss is None:
                    Parent.SendStreamMessage(
                        self.format_message("{0}, no target exists with that character name", username))
                    return
                else:
                    if fight1 is not None:
                        Parent.SendStreamMessage(self.format_message(
                            "{0}, you are being attacked or attacking someone, either way, too hard to focus on the" +
                            " boss now",
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
                            Attack.create(self.ATTACK_ACTION, attacker.char_id, boss_id=boss.boss_id,
                                          resolve_time=resolve_time, connection=conn)
                            return
            if target.position == attacker.position:
                if fight1 is not None:
                    if fight1.attacker_id == attacker.char_id:
                        Parent.SendStreamMessage(self.format_message(
                            "{0}, you are already attacking someone",
                            username))
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
        conn.close()

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
            if defender.is_stunned():
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you cannot defend while stunned!",
                    username
                ))
                return
            fight = Attack.find_by_target(defender, conn)
            if fight is None:
                Parent.SendStreamMessage("you are currently not being attacked")
                return
            else:
                Attack.create(self.DEFEND_ACTION, defender.char_id, resolver_id=fight.resolver_id, connection=conn)
        conn.close()

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
            if countermen.is_stunned():
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you cannot counter while stunned!",
                    username
                ))
                return
            fight = Attack.find_by_target(countermen, conn)
            if fight is None:
                Parent.SendStreamMessage("you are currently not being attacked")
                return
            else:
                Attack.create(self.COUNTER_ACTION, countermen.char_id, resolver_id=fight.resolver_id, connection=conn)
        conn.close()

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
            if flee_char.is_stunned():
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you cannot flee while stunned!",
                    username
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
        conn.close()

    def look(self, _, username, target_name):
        with self.get_connection() as conn:
            target_char = Character.find_by_name(target_name, conn)
            if target_name is None:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, there is no character with the name {1}",
                    username,
                    target_name
                ))
                return
            equipment_str = "badly equipped for hes lvl"

            equipment_lvl = 0
            if target_char.weapon is not None:
                equipment_lvl += target_char.weapon.min_lvl
            if target_char.armor is not None:
                equipment_lvl += target_char.armor.min_lvl

            if equipment_lvl >= target_char.lvl*1.5:
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
        conn.close()

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
                    if amount >= 2 * bounty.reward and bounty.kill_count > 1:  # TODO: other way around
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
        conn.close()

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
        conn.close()

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
    #   specials functions
    # ---------------------------------------
    def stun(self, user_id, username, target_name):
        with self.get_connection() as conn:
            char = Character.find_by_user(user_id, conn)
            if char is None:
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
                return
            if char.is_stunned():
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you use specials while stunned!",
                    username
                ))
                return
            target = Character.find_by_name(target_name, conn)
            if target is None:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, there is no character called {1}",
                    username,
                    target_name
                ))
                return
            char.use_special(Special.Specials.STUN, target)
        conn.close()

    def track(self, user_id, username, target_name):
        with self.get_connection() as conn:
            char = Character.find_by_user(user_id, conn)
            if char is None:
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
                return
            if char.is_stunned():
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you use specials while stunned!",
                    username
                ))
                return
            target = Character.find_by_name(target_name, conn)
            if target is None:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, there is no character called {1}",
                    username,
                    target_name
                ))
                return
            char.use_special(Special.Specials.TRACK, target)
        conn.close()

    def guardian(self, user_id, username, target_name=None):
        with self.get_connection() as conn:
            char = Character.find_by_user(user_id, conn)
            if char is None:
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
                return
            if char.is_stunned():
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you use specials while stunned!",
                    username
                ))
                return
            if target_name is None:
                target = char
            else:
                target = Character.find_by_name(target_name, conn)
                if target is None:
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, there is no character called {1}",
                        username,
                        target_name
                    ))
                    return
            char.use_special(Special.Specials.GUARDIAN, target)
        conn.close()

    def empower(self, user_id, username, target_name=None):
        with self.get_connection() as conn:
            char = Character.find_by_user(user_id, conn)
            if char is None:
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
                return
            if char.is_stunned():
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you use specials while stunned!",
                    username
                ))
                return
            if target_name is None:
                target = char
            else:
                target = Character.find_by_name(target_name, conn)
                if target is None:
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, there is no character called {1}",
                        username,
                        target_name
                    ))
                    return
            char.use_special(Special.Specials.EMPOWER, target)
        conn.close()

    def repel(self, user_id, username, target_name=None):
        with self.get_connection() as conn:
            char = Character.find_by_user(user_id, conn)
            if char is None:
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
                return
            if target_name is None:
                target = char
            else:
                target = Character.find_by_name(target_name, conn)
                if target is None:
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, there is no character called {1}",
                        username,
                        target_name
                    ))
                    return
            char.use_special(Special.Specials.REPEL, target)
        conn.close()

    def blind(self, user_id, username, target_name):
        with self.get_connection() as conn:
            char = Character.find_by_user(user_id, conn)
            if char is None:
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
                return
            if char.is_stunned():
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you use specials while stunned!",
                    username
                ))
                return
            target = Character.find_by_name(target_name, conn)
            if target is None:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, there is no character called {1}",
                    username,
                    target_name
                ))
                return
            char.use_special(Special.Specials.BLIND, target)
        conn.close()

    def curse(self, user_id, username, target_name):
        with self.get_connection() as conn:
            char = Character.find_by_user(user_id, conn)
            if char is None:
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
                return
            if char.is_stunned():
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you use specials while stunned!",
                    username
                ))
                return
            target = Character.find_by_name(target_name, conn)
            if target is None:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, there is no character called {1}",
                    username,
                    target_name
                ))
                return
            char.use_special(Special.Specials.CURSE, target)
        conn.close()

    def invis(self, user_id, username, target_name=None):
        with self.get_connection() as conn:
            char = Character.find_by_user(user_id, conn)
            if char is None:
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
                return
            if char.is_stunned():
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you use specials while stunned!",
                    username
                ))
                return
            if target_name is None:
                target = char
            else:
                target = Character.find_by_name(target_name, conn)
                if target is None:
                    Parent.SendStreamMessage(self.format_message(
                        "{0}, there is no character called {1}",
                        username,
                        target_name
                    ))
                    return
            char.use_special(Special.Specials.INVIS, target)
        conn.close()

    def steal(self, user_id, username, target_name):
        with self.get_connection() as conn:
            char = Character.find_by_user(user_id, conn)
            if char is None:
                Parent.SendStreamMessage(self.format_message(
                    self.scriptSettings.no_character_yet,
                    username,
                    self.scriptSettings.create_command
                ))
                return
            if char.is_stunned():
                Parent.SendStreamMessage(self.format_message(
                    "{0}, you use specials while stunned!",
                    username
                ))
                return
            target = Character.find_by_name(target_name, conn)
            if target is None:
                Parent.SendStreamMessage(self.format_message(
                    "{0}, there is no character called {1}",
                    username,
                    target_name
                ))
                return
            char.use_special(Special.Specials.STEAL, target)
        conn.close()

    # ---------------------------------------
    #   auxiliary functions
    # ---------------------------------------
    def format_message(self, msg, *args, **kwargs):
        if self.scriptSettings.add_me:
            msg = "/me " + msg
        return msg.format(*args, **kwargs)