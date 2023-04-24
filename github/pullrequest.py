import functools

from github.base import GithubApiBase
from github.base import GithubEndpointResponse


class PullRequest(GithubEndpointResponse):
    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.state = self._data["state"]

    @functools.cached_property
    def closed(self) -> bool:
        return self.state.lower() == "closed"


class GithubPullRequestApi(GithubApiBase):
    def __init__(self, token: str) -> None:
        super().__init__(token)
        self._ENDPOINT = (
            "https://api.github.com/repos/{OWNER}/{REPO}/pulls/{PULL_NUMBER}"
        )

    def get(self, owner: str, repo: str, number: int) -> PullRequest:
        endpoint = self._ENDPOINT.format(OWNER=owner, REPO=repo, PULL_NUMBER=number)
        resp = self._client.get(endpoint)
        resp.raise_for_status()
        return PullRequest(resp.json())

    def closed_pulls(self, owner: str, repo: str, number: int) -> list[PullRequest]:
        endpoint = (
            self._ENDPOINT.format(OWNER=owner, REPO=repo, PULL_NUMBER=number)
            + "?state=closed&per_page=100"
        )
        resp = self._read_all_pages(endpoint)
        resp.raise_for_status()
        return [PullRequest(x) for x in resp.json()]

    def open_pulls(self, owner: str, repo: str, number: int) -> list[PullRequest]:
        endpoint = (
            self._ENDPOINT.format(OWNER=owner, REPO=repo, PULL_NUMBER=number)
            + "?state=open&per_page=100"
        )
        resp = self._read_all_pages(endpoint)
        resp.raise_for_status()
        return [PullRequest(x) for x in resp.json()]
