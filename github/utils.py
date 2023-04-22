from datetime import datetime


def datestr2date(value: str) -> datetime:
    """
    Parses the API returned date string to a Python datetime, handling
    the Z notation for Zulu (UTC) time
    """
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
