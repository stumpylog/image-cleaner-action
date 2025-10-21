import logging
import math
from argparse import ArgumentParser
from typing import Final


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


def bytes_to_human_readable(size_bytes: int | float, precision: int = 2) -> str:
    """
    Converts a size in bytes to a human-readable string (e.g., 1024 -> 1.00 KiB).

    Args:
        size_bytes: The size in bytes (int or float).
        precision: The number of decimal places for the result.

    Returns:
        A string representing the size in a human-readable format.
    """
    if size_bytes < 0:
        return "Invalid size"
    if size_bytes == 0:
        return "0 Bytes"

    UNITS: Final[list[str]] = ["Bytes", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB"]
    BASE: Final[int] = 1024

    try:
        # Calculate the unit index. math.log2(x) is equivalent to log(x, 2).
        # Dividing by 10 determines how many times we've passed the 1024 threshold (2^10).
        unit_index: int = math.floor(math.log2(size_bytes) / 10)
    except ValueError:
        # Should only happen if size_bytes is 0 or negative, but included for robustness
        return "0 Bytes"

    # Ensure the index doesn't go beyond the largest unit defined
    unit_index = min(unit_index, len(UNITS) - 1)

    # Calculate the converted size
    converted_size: float = size_bytes / (BASE**unit_index)
    unit: str = UNITS[unit_index]

    # Format the output string using f-string with a nested f-string for dynamic precision
    return f"{converted_size:.{precision}f} {unit}"
