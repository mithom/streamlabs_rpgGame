import clr
clr.AddReference("IronPython.SQLite.dll")


class RpgGame(object):
    def __init__(self, script_settings):
        self.scriptSettings = script_settings

    def load_or_init_game(self):
        pass

    def apply_reload(self):
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


class Specials(object):
    def __init__(self):
        pass
