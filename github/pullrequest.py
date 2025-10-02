import functools

from github.base import GithubApiBase
from github.base import GithubEndpointResponse
from github.models.pullrequest import SimplePullRequest


class PullRequest(GithubEndpointResponse):
    def __init__(self, data: SimplePullRequest) -> None:
        super().__init__(data)  # type: ignore[arg-type]
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
        # resp is a list of dicts here
        resp: list[SimplePullRequest] = self._read_all_pages(endpoint, query_params=query_params)
        # No raise_for_status() or .json() needed on the list itself
        return [PullRequest(x) for x in resp]

    def open_pulls(self, owner: str, repo: str) -> list[PullRequest]:
        endpoint = self.LIST_PR_API_ENDPOINT.format(OWNER=owner, REPO=repo)
        query_params = {"state": "open", "per_page": 100}
        # resp is a list of dicts here
        resp: list[SimplePullRequest] = self._read_all_pages(endpoint, query_params=query_params)
        # No raise_for_status() or .json() needed on the list itself
        return [PullRequest(x) for x in resp]
