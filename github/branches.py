import logging

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


class GithubBranchApi(GithubApiBase):
    """
    Wrapper around branch API.

    See https://docs.github.com/en/rest/branches/branches

    """

    def __init__(self, token: str) -> None:
        super().__init__(token)

        self._ENDPOINT = "https://api.github.com/repos/{OWNER}/{REPO}/branches"

    def branches(self, owner: str, repo: str) -> list[GithubBranch]:
        """
        Returns all current branches of the given repository owned by the given
        owner or organization.
        """
        # The environment GITHUB_REPOSITORY already contains the owner in the correct location
        endpoint = self._ENDPOINT.format(OWNER=owner, REPO=repo)
        internal_data = self._read_all_pages(endpoint)
        return [GithubBranch(branch) for branch in internal_data]
