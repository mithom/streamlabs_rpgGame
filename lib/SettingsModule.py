import json
import codecs

Parent = None


class Settings(object):
    # do not use multiple instances of this version of the class, as it uses class
    # variables in order to avoid being in __dict__
    settings_file = ""
    script_name = ""

    def __init__(self, settings_file, script_name):
        Settings.settings_file = settings_file
        Settings.script_name = script_name
        try:
            with codecs.open(self.settings_file, encoding="utf-8-sig", mode="r") as f:
                self.__dict__ = json.load(f, encoding="utf-8")
        except:
            # Config
            self.test_offline = False
            self.update_interval = 1
            self.only_active = True
            self.add_me = True
            self.piebank_name = "piebank"

            # Gameplay
            self.fight_resolve_time = 20
            self.xp_farm_time = 60
            self.starting_location = "Town"

            # traits
            self.durable_enabled = True
            self.durable_name = "Durable"
            self.strong_enabled = True
            self.strong_name = "Strong"
            self.wise_enabled = True
            self.wise_name = "Wise"
            self.greedy_enabled = True
            self.greedy_name = "Greedy"
            self.alert_enabled = True
            self.alert_name = "Alert"
            self.lucky_enabled = True
            self.lucky_name = "Lucky"
            self.violent_enabled = True
            self.violent_name = "Violent"
            self.pacifist_enabled = True
            self.pacifist_name = "Pacifist"
            # TODO: add button to open data folder

            # command names
            # 0 args
            self.info_command = "!info"
            self.condensed_info_command = "!i"
            self.stat_command = "!stat"
            self.defend_command = "!defend"
            self.counter_command = "!counter"
            self.flee_command = "!flee"
            self.dough_command = "!dough"
            self.queen_command = "!queen"
            self.king_command = "!king"

            # 1 arg
            self.create_command = "!create"
            self.move_command = "!move"
            self.buy_command = "!buy"
            self.attack_command = "!attack"
            self.look_command = "!look"
            self.tax_command = "!tax"
            self.vote_command = "!vote"
            self.smite_command = "smite"
            self.unsmite_command = "!unsmite"

            # 2 args
            self.give_command = "!give"
            self.bounty_command = "!bounty"

            # responses, TODO: add to ui_config
            self.no_character_yet = "{0}, you don't have a character yet, create one by typing {1} {{name}}"

    def reload(self, json_data):
        """ Reload settings from Chatbot user interface by given json data. """
        self.__dict__ = json.loads(json_data, encoding="utf-8")
        self.save()
        return

    def save(self):
        """ Save settings contained within to .json and .js settings files. """
        try:
            with codecs.open(self.settings_file, encoding="utf-8-sig", mode="w+") as f:
                json.dump(self.__dict__, f, encoding="utf-8", ensure_ascii=False)
            with codecs.open(self.settings_file.replace("json", "js"), encoding="utf-8-sig", mode="w+") as f:
                f.write("var settings = {0};".format(json.dumps(self.__dict__, encoding='utf-8', ensure_ascii=False)))
        except:
            Parent.Log(self.script_name, "Failed to save settings to file.")
        return
