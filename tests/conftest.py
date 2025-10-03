import pytest_asyncio

from github.base import GithubApiBase
from github.branches import GithubBranchApi
from github.packages import GithubContainerRegistryOrgApi
from github.packages import GithubContainerRegistryUserApi
from github.pullrequest import GithubPullRequestApi
from github.ratelimit import GithubRateLimitApi

# --- Constants for Mock Fixtures ---
MOCK_TOKEN = "test_conftest_token"
MOCK_OWNER = "test-conftest-owner"


@pytest_asyncio.fixture
async def base_api():
    """Provides a GithubApiBase instance."""
    async with GithubApiBase(token=MOCK_TOKEN) as api:
        yield api


@pytest_asyncio.fixture
async def branch_api():
    """Provides a GithubBranchApi instance."""
    async with GithubBranchApi(token=MOCK_TOKEN) as api:
        yield api


@pytest_asyncio.fixture
async def org_packages_api():
    """Provides a GithubContainerRegistryOrgApi instance for an organization."""
    async with GithubContainerRegistryOrgApi(
        token=MOCK_TOKEN,
        owner_or_org=f"{MOCK_OWNER}-org",
        is_org=True,
    ) as api:
        yield api


@pytest_asyncio.fixture
async def user_packages_api():
    """Provides a GithubContainerRegistryUserApi instance for a user."""
    async with GithubContainerRegistryUserApi(
        token=MOCK_TOKEN,
        owner_or_org=f"{MOCK_OWNER}-user",
        is_org=False,
    ) as api:
        yield api


@pytest_asyncio.fixture
async def pr_api():
    """Provides a GithubPullRequestApi instance."""
    async with GithubPullRequestApi(token=MOCK_TOKEN) as api:
        yield api


@pytest_asyncio.fixture
async def ratelimit_api():
    """Provides a GithubRateLimitApi instance."""
    async with GithubRateLimitApi(token=MOCK_TOKEN) as api:
        yield api
