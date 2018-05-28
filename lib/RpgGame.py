from StaticData import Location, Weapon, Armor
from characters import Character
import os

import clr

clr.AddReference("IronPython.SQLite.dll")
import sqlite3

Parent = None


class RpgGame(object):
    def __init__(self, script_settings, script_name, db_directory):
        self.scriptSettings = script_settings
        self.script_name = script_name
        self.db_directory = db_directory

        # Prepare everything
        self.prepare_database()
        self.create_and_load_static_data()

    def get_connection(self):
        return sqlite3.connect(os.path.join(self.db_directory, "database.db"))

    def prepare_database(self):
        conn = self.get_connection()
        try:
            # create all tables, location first, because character got foreign key to this
            Location.create_table_if_not_exists(conn)
            Character.create_table_if_not_exists(conn)
            Weapon.create_table_if_not_exists(conn)
            Armor.create_table_if_not_exists(conn)
        finally:
            conn.close()

    def create_and_load_static_data(self):
        conn = self.get_connection()
        Location.create_locations(self.scriptSettings, conn)
        pass

    def apply_reload(self):
        pass

    def tick(self):
        if self.scriptSettings.only_active:
            result = Parent.GetActiveUsers()
        else:
            result = Parent.GetViewerList()
        conn = self.get_connection()
        try:
            for user_id in result:
                char = Character.find_by_user(user_id, conn)
                if char is None:
                    town = filter(lambda loc: loc.name == "Town", Location.load_locations(conn))[0]
                    char = Character.create("test", user_id, town.location_id, conn)
                Parent.SendStreamMessage(self.format_message("{0} zijn char {1} met id {2} zit in de zone: {3}" %
                                                             char.user_id, char.name, char.char_id, char.location.name))
        finally:
            conn.close()

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
        conn = self.get_connection()
        character = Character.find_by_user(user_id, conn)
        location = character.location
        Parent.SendStreamMessage(self.format_message(
            "{0}, your character {1} is located in {2} with difficulty {3}",
            username,
            character.name,
            location.name,
            location.difficulty
        ))
        conn.close()

    def condensed_info(self, user_id, username):
        conn = self.get_connection()
        character = Character.find_by_user(user_id, conn)
        Parent.SendStreamMessage(self.format_message(
            "{0}, your character {1} is located in {2}",
            username,
            character.name,
            character.location.name
        ))
        conn.close()

    def move(self, user_id, username, location_name):
        conn = self.get_connection()
        location = Location.find_by_name(location_name)
        character = Character.find_by_user(user_id, conn)
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
        conn.close()

    def buy(self, user_id, username, item_name):
        conn = self.get_connection()
        character = Character.find_by_user(user_id, conn)
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
        conn.close()

    def attack(self, user_id, username, target_name):
        pass

    def defend(self, user_id, username):
        pass

    def counter(self, user_id, username):
        pass

    def flee(self, user_id, username):
        pass

    def look(self, user_id, username, target_name):
        pass

    def dough(self, user_id, username):
        pass

    def give(self, user_id, username, amount, recipient_name):
        pass

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
