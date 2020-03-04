from functools import wraps

Parent = None
scriptSettings = None
ScriptName = None


def send_stream_message(f, nb_return_args=0, message=None):
    @wraps(f)
    def message_wrapper(*args, **kwargs):
        value = f(*args, **kwargs)
        if hasattr(value, '__len__') and len(value) > nb_return_args:
            if message is None:
                Parent.SendStreamMessage(format_message(*value[nb_return_args:]))
            else:
                Parent.SendStreamMessage(format_message(message, *value[nb_return_args:]))
            return value[:nb_return_args]
        elif nb_return_args == 0 and value is not None:
            if message is None:
                Parent.SendStreamMessage(format_message(value))
            else:
                Parent.SendStreamMessage(format_message(message, value))
        else:
            if message is not None:
                Parent.SendStreamMessage(format_message(message))
            return value
    return message_wrapper


def cooldown(f, seconds, on_success=False, hook=None):
    hook = hook
    if hook is None:
        hook = f.__name__

    def success():
        Parent.Cooldown(seconds, ScriptName, hook)

    @wraps(f)
    def cd_wrapper(*args, **kwargs):
        if Parent.IsOnCooldown(ScriptName, hook):
            if not on_success:
                Parent.Cooldown(seconds, ScriptName, hook)
                return f(*args, success=success, **kwargs)
            else:
                Parent.Cooldown(seconds, ScriptName, hook)
    return cd_wrapper


def format_message(msg, *args, **kwargs):
    if scriptSettings.add_me and not kwargs.get('whisper', False):
        msg = "/me " + msg
    return msg.format(*args, **kwargs)
