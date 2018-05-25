import Items
import Locations
import os

import clr
clr.AddReference("IronPython.SQLite.dll")
import sqlite3


class RpgGame(object):
    def __init__(self, script_settings, script_name, db_directory):
        self.scriptSettings = script_settings
        self.conn = sqlite3.connect(os.path.join(db_directory, "database.db"))
        self.script_name = script_name

    def load_or_init_game(self):
        pass

    def apply_reload(self):
        pass

    def tick(self):
        pass


class Character(object):
    def __init__(self):
        pass


class Boss(object):
    def __init__(self):
        pass


class Roshan(Boss):
    def __init__(self):
        super(Roshan, self).__init__()
        pass


class Traits(object):
    def __init__(self):
        pass


class Specials(object):
    def __init__(self):
        pass