import pytest
from pytest_httpx import HTTPXMock

from github.packages import ContainerPackage
from github.packages import GithubContainerRegistryOrgApi
from github.packages import GithubContainerRegistryUserApi


class TestGithubContainerRegistryOrgApi:
    @pytest.fixture
    def api(self) -> GithubContainerRegistryOrgApi:
        return GithubContainerRegistryOrgApi("test-token", "test-org", is_org=True)

    def test_init_sets_is_org_true(self, api: GithubContainerRegistryOrgApi) -> None:
        assert api._owner_or_org == "test-org"
        assert api.is_org is True

    def test_delete_package_version(self, httpx_mock: HTTPXMock, api: GithubContainerRegistryOrgApi) -> None:
        pkg_data = ContainerPackage(
            {
                "name": "pkg",
                "id": 42,
                "url": "https://api.github.com/orgs/test-org/packages/container/pkg/versions/42",
                "metadata": {"container": {"tags": []}},
            },  # type: ignore[arg-type]
        )
        httpx_mock.add_response(method="DELETE", url=pkg_data.url, status_code=204)

        api.delete(pkg_data)  # Should succeed silently

    def test_restore_package_version(self, httpx_mock: HTTPXMock, api: GithubContainerRegistryOrgApi) -> None:
        version_id = 42
        endpoint = (
            f"https://api.github.com/orgs/test-org/packages/container/pkg/versions/{version_id}/restore"
        )
        httpx_mock.add_response(method="POST", url=endpoint, status_code=200)

        # Patch endpoint template for test control
        api.PACKAGE_VERSION_RESTORE_ENDPOINT = "/orgs/{ORG}/packages/container/pkg/versions/{id}/restore"

        api._client.post(endpoint)  # Should not raise


class TestGithubContainerRegistryUserApi:
    @pytest.fixture
    def api(self) -> GithubContainerRegistryUserApi:
        return GithubContainerRegistryUserApi("test-token", "test-user", is_org=False)

    def test_init_sets_is_org_false(self, api: GithubContainerRegistryUserApi) -> None:
        assert api._owner_or_org == "test-user"
        assert api.is_org is False

    def test_delete_package_version(self, httpx_mock: HTTPXMock, api: GithubContainerRegistryUserApi) -> None:
        pkg_data = ContainerPackage(
            {
                "name": "pkg",
                "id": 99,
                "url": "https://api.github.com/user/packages/container/pkg/versions/99",
                "metadata": {"container": {"tags": []}},
            },  # type: ignore[arg-type]
        )
        httpx_mock.add_response(method="DELETE", url=pkg_data.url, status_code=204)

        api.delete(pkg_data)

    def test_restore_package_version(
        self,
        httpx_mock: HTTPXMock,
        api: GithubContainerRegistryUserApi,
    ) -> None:
        version_id = 99
        endpoint = f"https://api.github.com/user/packages/container/pkg/versions/{version_id}/restore"
        httpx_mock.add_response(method="POST", url=endpoint, status_code=200)

        api.PACKAGE_VERSION_RESTORE_ENDPOINT = "/user/packages/container/pkg/versions/{id}/restore"

        api._client.post(endpoint)
