import functools
import logging
import re

from github.base import GithubApiBase
from github.base import GithubEndpointResponse

logger = logging.getLogger(__name__)


class GithubBranch(GithubEndpointResponse):
    """
    Simple wrapper for a repository branch, only extracts name information
    for now.
    """

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.name = self._data["name"]

    def __str__(self) -> str:
        return f"Branch {self.name}"

    @functools.cache
    def matches(self, pattern: str) -> bool:
        return re.match(pattern, self.name) is not None


class GithubBranchApi(GithubApiBase):
    """
    Wrapper around branch API.

    See https://docs.github.com/en/rest/branches/branches

    """

    API_ENDPOINT = "/repos/{OWNER}/{REPO}/branches"

    def __init__(self, token: str) -> None:
        super().__init__(token)

    def branches(self, owner: str, repo: str) -> list[GithubBranch]:
        """
        Returns all current branches of the given repository owned by the given
        owner or organization.
        """
        # The environment GITHUB_REPOSITORY already contains the owner in the correct location
        internal_data = self._read_all_pages(
            self.API_ENDPOINT.format(OWNER=owner, REPO=repo),
        )
        return [GithubBranch(branch) for branch in internal_data]
