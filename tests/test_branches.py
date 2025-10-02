import pytest

from github.branches import GithubBranch
from github.branches import GithubBranchApi


class TestGithubBranchApi:
    @pytest.fixture
    def api(self, branch_api):
        return branch_api

    @pytest.mark.asyncio
    async def test_branches_success(self, httpx_mock, api: GithubBranchApi):
        response_data = [{"name": "main"}, {"name": "dev"}]
        httpx_mock.add_response(json=response_data)

        result = await api.branches("owner", "repo")

        assert isinstance(result, list)
        assert all(isinstance(branch, GithubBranch) for branch in result)
        assert [b._data["name"] for b in result] == ["main", "dev"]

    def test_branch_str(self):
        branch = GithubBranch({"name": "feature-x"})
        assert branch.name == "feature-x"

    def test_branch_matches(self):
        branch = GithubBranch({"name": "fix-123"})
        assert branch.matches(r"fix-\d+")
        assert not branch.matches(r"feature/.*")
