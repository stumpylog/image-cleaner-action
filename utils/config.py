import logging
from argparse import Namespace
from dataclasses import dataclass
from dataclasses import field
from enum import StrEnum

from utils import coerce_to_bool
from utils import get_log_level


class Scheme(StrEnum):
    BRANCH = "branch"
    PULL_REQUEST = "pull_request"


@dataclass(slots=True)
class BaseConfig:
    """Base configuration shared by all cleanup actions."""

    token: str
    owner_or_org: str
    package_name: str
    delete: bool = False
    is_org: bool = False
    log_level: int = field(default=logging.INFO)

    # Raw values from args before conversion
    _raw_delete: str = field(default="false", repr=False)
    _raw_is_org: str = field(default="false", repr=False)
    _raw_log_level: str = field(default="info", repr=False)

    def __post_init__(self) -> None:
        """Convert string inputs to proper types after initialization."""
        self.delete = coerce_to_bool(self._raw_delete)
        self.is_org = coerce_to_bool(self._raw_is_org)
        self.log_level = get_log_level(self._raw_log_level)

    @classmethod
    def from_args(cls, args: Namespace) -> "BaseConfig":
        """Factory method to create config from parsed arguments."""
        return cls(
            token=args.token,
            owner_or_org=args.owner,
            package_name=args.name,
            _raw_delete=args.delete,
            _raw_is_org=args.is_org,
            _raw_log_level=args.loglevel,
        )
