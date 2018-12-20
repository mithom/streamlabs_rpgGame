# ---------------------------------------
#   Import Libraries
# ---------------------------------------
import os
import time
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))  # Point at lib folder for classes / references
import clr
clr.AddReference("IronPython.Modules.dll")

import RpgGame
import SettingsModule

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
m_settings_file = os.path.join(os.path.dirname(__file__), "Settings", "rpg_settings.json")
ScriptSettings = None
game = None
next_update = 0


# ---------------------------------------
#   main interface
# ---------------------------------------
# noinspection PyPep8Naming
def Init():
    global ScriptSettings, game, next_update
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

    # Create game
    game = RpgGame.RpgGame(ScriptSettings, ScriptName, db_directory)

    # Prepare Tick()
    next_update = time.time()


# noinspection PyPep8Naming
def ReloadSettings(jsondata):
    ScriptSettings.reload(jsondata)
    game.apply_reload()


# noinspection PyPep8Naming
def Unload():
    ScriptSettings.save()


# noinspection PyPep8Naming
def ScriptToggle(state):
    global next_update
    # next_update is time remaining in tick while script is toggled off.
    if state:
        next_update += time.time()
    else:
        next_update -= time.time()


# noinspection PyPep8Naming
def Tick():
    if Parent.IsLive() or ScriptSettings.test_offline:
        if time.time() >= next_update:
            set_next_update()
            game.tick()


# noinspection PyPep8Naming
def Execute(data):
    if data.IsChatMessage():
        p_count = data.GetParamCount()
        command_functions = game.commands()
        if p_count <= len(command_functions):
            param0 = data.GetParam(0)
            if param0 in command_functions[p_count-1]:
                command_functions[p_count-1][param0](data.User, data.UserName, *data.Message.split()[1:])


def OpenDataFolder():
    os.startfile(os.path.join(os.path.dirname(__file__), "data"))


push_time = 0
push_count = 0


def ResetDatabase():
    global push_time, push_count
    if time.time() > push_time:
        push_count = 0
        push_time = time.time() + 5
    push_count += 1
    if push_count >= 5:
        game.reset_db()
        Init()


# ---------------------------------------
#   auxiliary functions
# ---------------------------------------
def set_next_update():
    global next_update
    next_update = time.time() + ScriptSettings.update_interval
