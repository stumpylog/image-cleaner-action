import logging
from argparse import ArgumentParser


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


def common_args(description: str) -> ArgumentParser:
    """
    Constructs an ArgumentParser with the common args to each action's
    main entry
    """
    parser = ArgumentParser(
        description=description,
    )

    # Get the PAT token
    parser.add_argument(
        "--token",
        help="Personal Access Token with the OAuth scope for packages:delete",
        required=True,
    )

    # Requires an affirmative command to actually do a delete
    parser.add_argument(
        "--delete",
        default=False,
        help="If provided, actually delete the container tags",
    )

    # If true, the owner is an organization
    parser.add_argument(
        "--is-org",
        default=False,
        help="If True, the owner of the package is an organization",
    )

    # Get the name of the package being processed this round
    parser.add_argument(
        "--name",
        help="The package to process",
        required=True,
    )

    # Allows configuration of log level for debugging
    parser.add_argument(
        "--loglevel",
        default="info",
        help="Configures the logging level",
    )

    # Get the name of the package owner
    parser.add_argument(
        "--owner",
        help="The owner of the package, either the user or the org",
    )

    return parser
