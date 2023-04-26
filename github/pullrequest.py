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
    GET_PR_API_ENDPOINT = "/repos/{OWNER}/{REPO}/pulls/{PULL_NUMBER}"
    LIST_PR_API_ENDPOINT = "/repos/{OWNER}/{REPO}/pulls"

    def get(self, owner: str, repo: str, number: int) -> PullRequest:
        endpoint = self.GET_PR_API_ENDPOINT.format(
            OWNER=owner,
            REPO=repo,
            PULL_NUMBER=number,
        )
        resp = self._client.get(endpoint)
        resp.raise_for_status()
        return PullRequest(resp.json())

    def closed_pulls(self, owner: str, repo: str) -> list[PullRequest]:
        endpoint = self.LIST_PR_API_ENDPOINT.format(OWNER=owner, REPO=repo)
        query_params = {"state": "closed", "per_page": 100}
        resp = self._read_all_pages(endpoint, query_params=query_params)
        resp.raise_for_status()
        return [PullRequest(x) for x in resp.json()]

    def open_pulls(self, owner: str, repo: str) -> list[PullRequest]:
        endpoint = self.LIST_PR_API_ENDPOINT.format(OWNER=owner, REPO=repo)
        query_params = {"state": "closed", "per_page": 100}
        resp = self._read_all_pages(endpoint, query_params=query_params)
        resp.raise_for_status()
        return [PullRequest(x) for x in resp.json()]
