import json
import codecs


class Settings(object):
    def __init__(self, settings_file, script_name):
        global log
        self.script_name = script_name
        self.settings_file = settings_file

        try:
            with codecs.open(self.settings_file, encoding="utf-8-sig", mode="r") as f:
                self.__dict__ = json.load(f, encoding="utf-8")
        except:
            #config
            self.test_offline = False
            self.update_interval = 60

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

    def reload(self, jsondata):
        """ Reload settings from Chatbot user interface by given json data. """
        self.__dict__ = json.loads(jsondata, encoding="utf-8")
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