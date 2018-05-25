# ---------------------------------------
#   Import Libraries
# ---------------------------------------
import os
import time

sys.path.append(os.path.join(os.path.dirname(__file__), "lib")) #point at lib folder for classes / references
import clr
clr.AddReference("IronPython.Modules.dll")

from RpgGame import RpgGame
from SettingsModule import Settings
from Commands import commands

# ---------------------------------------
#   [Required]  Script Information
# ---------------------------------------
ScriptName = "rpgGame"
Website = "https://www.twitch.tv/mi_thom"
Description = "a chatbot rpg game based on Kaylovespie's Pieland game"
Creator = "mi_thom"
Version = "0.0.1"

# ---------------------------------------
#   Global Variables
# ---------------------------------------
m_settings_file = os.path.join(os.path.dirname(__file__), "Settings\settings.json")
ScriptSettings = Settings(m_settings_file)
game = None


# ---------------------------------------
#   main interface
# ---------------------------------------
def Init():
    global ScriptSettings, game

    #   Create Settings Directory
    directory = os.path.join(os.path.dirname(__file__), "Settings")
    if not os.path.exists(directory):
        os.makedirs(directory)

    #   Load settings
    ScriptSettings = Settings(m_settings_file)
    game = RpgGame(ScriptSettings)


def ReloadSettings(jsondata):
    ScriptSettings.reload(jsondata)
    game.apply_reload()


def Unload():
    ScriptSettings.save()


def ScriptToggle(boolean):
    pass


def Tick():
    pass


def Execute(data):
    if data.IsChatMessage():
        p_count = data.GetParamCount()
        if p_count <= len(commands):
        param0 = data.GetParam(0)
        if param0 in commands[p_count-1]:
            commands[p_count](*data.Message.split()[1:])

