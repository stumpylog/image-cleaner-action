from datetime import datetime


def datestr2date(value: str) -> datetime:
    """
    Parses the API returned date string to a Python datetime.  The Z notation
    for Zulu (UTC) time is handled natively by fromisoformat
    """
    return datetime.fromisoformat(value)
