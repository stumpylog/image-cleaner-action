import pytest

from github.pullrequest import GithubPullRequestApi
from github.pullrequest import PullRequest


class TestGithubPullRequestApi:
    @pytest.mark.asyncio
    async def test_get_pull_request(self, httpx_mock, pr_api: GithubPullRequestApi):
        pr_json = {"number": 42, "state": "closed"}
        httpx_mock.add_response(json=pr_json)

        pr = await pr_api.get("owner", "repo", 42)
        assert isinstance(pr, PullRequest)
        assert pr._data["number"] == 42
        assert pr.closed
        assert pr.state == "closed"

    def test_closed_property(self):
        pr = PullRequest({"state": "closed"})
        assert pr.closed

        pr = PullRequest({"state": "open"})
        assert not pr.closed

    @pytest.mark.asyncio
    async def test_closed_pulls(self, httpx_mock, pr_api: GithubPullRequestApi):
        httpx_mock.add_response(json=[{"state": "closed"}])
        pulls = await pr_api.closed_pulls("owner", "repo")
        assert len(pulls) == 1
        assert all(p.closed for p in pulls)

    @pytest.mark.asyncio
    async def test_open_pulls(self, httpx_mock, pr_api: GithubPullRequestApi):
        httpx_mock.add_response(json=[{"state": "open"}])
        pulls = await pr_api.open_pulls("owner", "repo")
        assert len(pulls) == 1
        assert all(not p.closed for p in pulls)
