# ---------------------------------------
#   Import Libraries
# ---------------------------------------
import os
import time
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "lib")) #point at lib folder for classes / references
import clr
clr.AddReference("IronPython.Modules.dll")

import RpgGame
import SettingsModule
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
ScriptSettings = None
game = None
next_update = None


# ---------------------------------------
#   main interface
# ---------------------------------------
def Init():
    global ScriptSettings, game
    # Insert Parent in submodules
    RpgGame.Parent = Parent
    SettingsModule.Parent = Parent

    #   Create Settings and db Directory
    settings_directory = os.path.join(os.path.dirname(__file__), "Settings")
    if not os.path.exists(settings_directory):
        os.makedirs(settings_directory)

    db_directory = os.path.join(os.path.dirname(__file__), "db")
    if not os.path.exists(db_directory):
        os.makedirs(db_directory)

    #   Load settings
    ScriptSettings = SettingsModule.Settings(m_settings_file, ScriptName)
    game = RpgGame.RpgGame(ScriptSettings, ScriptName, db_directory)

    # Prepare Tick()
    set_next_update()


def ReloadSettings(jsondata):
    ScriptSettings.reload(jsondata)
    game.apply_reload()


def Unload():
    ScriptSettings.save()


def ScriptToggle(state):
    global next_update
    # next_update is time remaining in tick while script is toggled off.
    if state:
        next_update += time.time()
    else:
        next_update -= time.time()


def Tick():
    if Parent.IsLive() or ScriptSettings.test_offline:
        if time.time() > next_update:
            set_next_update()
            game.tick()


def Execute(data):
    if data.IsChatMessage():
        p_count = data.GetParamCount()
        command_functions = commands(ScriptSettings)
        if p_count <= len(command_functions):
            param0 = data.GetParam(0)
            if param0 in command_functions[p_count-1]:
                command_functions[p_count-1](*data.Message.split()[1:])


# ---------------------------------------
#   auxiliary functions
# ---------------------------------------
def set_next_update():
    global next_update
    next_update = time.time() + ScriptSettings.update_interval
