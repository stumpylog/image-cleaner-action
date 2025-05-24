import pytest

from github.base import GithubApiBase
from github.branches import GithubBranchApi
from github.packages import GithubContainerRegistryOrgApi
from github.packages import GithubContainerRegistryUserApi
from github.pullrequest import GithubPullRequestApi
from github.ratelimit import GithubRateLimitApi

# --- Constants for Mock Fixtures ---
MOCK_TOKEN = "test_conftest_token"
MOCK_OWNER = "test-conftest-owner"


@pytest.fixture
def base_api():
    """Provides a GithubApiBase instance."""
    with GithubApiBase(token=MOCK_TOKEN) as api:
        yield api


@pytest.fixture
def branch_api():
    """Provides a GithubBranchApi instance."""
    with GithubBranchApi(token=MOCK_TOKEN) as api:
        yield api


@pytest.fixture
def org_packages_api():
    """Provides a GithubContainerRegistryOrgApi instance for an organization."""
    with GithubContainerRegistryOrgApi(token=MOCK_TOKEN, owner_or_org=MOCK_OWNER, is_org=True) as api:
        yield api


@pytest.fixture
def user_packages_api():
    """Provides a GithubContainerRegistryUserApi instance for a user."""
    with GithubContainerRegistryUserApi(token=MOCK_TOKEN, owner_or_org=MOCK_OWNER, is_org=False) as api:
        yield api


@pytest.fixture
def pr_api():
    """Provides a GithubPullRequestApi instance."""
    with GithubPullRequestApi(token=MOCK_TOKEN) as api:
        yield api


@pytest.fixture
def ratelimit_api():
    """Provides a GithubRateLimitApi instance."""
    with GithubRateLimitApi(token=MOCK_TOKEN) as api:
        yield api
