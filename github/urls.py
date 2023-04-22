import enum
from typing import Final


class ApiEndPointType(enum.Enum):
    BRANCHES_LIST = enum.auto()
    BRANCHES_GET = enum.auto()
    PULLS_LIST = enum.auto()
    PULLS_GET = enum.auto()


API_HOST: Final[str] = "https://api.github.com"

BRANCH_ENDPOINT = "repos/{REPO}/branches"


def build_url_for(endpoint: ApiEndPointType, is_org: bool, **kwargs) -> str:
    pass
