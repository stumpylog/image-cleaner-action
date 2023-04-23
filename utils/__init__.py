import logging


def get_log_level(level_name: str) -> int:
    """
    Returns a logging level, based
    :param args:
    :return:
    """
    levels = {
        "critical": logging.CRITICAL,
        "error": logging.ERROR,
        "warn": logging.WARNING,
        "warning": logging.WARNING,
        "info": logging.INFO,
        "debug": logging.DEBUG,
    }
    level = levels.get(level_name.lower())
    if level is None:
        level = logging.INFO
    return level


def coerce_to_bool(value) -> bool:
    """
    Given a thing, try hard to convert it from something which looks boolean
    like, but it actually a string or something, to a boolean
    """
    if not isinstance(value, bool):
        if isinstance(value, str):
            return value.lower() in {"true", "1"}
        else:
            raise TypeError(type(value))
    return value
