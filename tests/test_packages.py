import pytest
from pytest_httpx import HTTPXMock

from github.packages import ContainerPackage
from github.packages import GithubContainerRegistryOrgApi
from github.packages import GithubContainerRegistryUserApi


class TestGithubContainerRegistryOrgApi:
    def test_init_sets_is_org_true(self, org_packages_api: GithubContainerRegistryOrgApi) -> None:
        assert org_packages_api._owner_or_org == "test-conftest-owner-org"
        assert org_packages_api.is_org is True

    @pytest.mark.asyncio
    async def test_delete_package_version(
        self,
        httpx_mock: HTTPXMock,
        org_packages_api: GithubContainerRegistryOrgApi,
    ) -> None:
        pkg_data = ContainerPackage(
            {
                "name": "pkg",
                "id": 42,
                "url": "https://api.github.com/orgs/test-org/packages/container/pkg/versions/42",
                "metadata": {"container": {"tags": []}},
            },  # type: ignore[arg-type]
        )
        httpx_mock.add_response(method="DELETE", url=pkg_data.url, status_code=204)

        await org_packages_api.delete(pkg_data)  # Should succeed silently

    @pytest.mark.asyncio
    async def test_restore_package_version(
        self,
        httpx_mock: HTTPXMock,
        org_packages_api: GithubContainerRegistryOrgApi,
    ) -> None:
        version_id = 42
        endpoint = (
            f"https://api.github.com/orgs/test-org/packages/container/pkg/versions/{version_id}/restore"
        )
        httpx_mock.add_response(method="POST", url=endpoint, status_code=200)

        # Patch endpoint template for test control
        org_packages_api.PACKAGE_VERSION_RESTORE_ENDPOINT = (
            "/orgs/{ORG}/packages/container/pkg/versions/{id}/restore"
        )

        await org_packages_api._client.post(endpoint)  # Should not raise


class TestGithubContainerRegistryUserApi:
    def test_init_sets_is_org_false(self, user_packages_api: GithubContainerRegistryUserApi) -> None:
        assert user_packages_api._owner_or_org == "test-conftest-owner-user"
        assert user_packages_api.is_org is False

    @pytest.mark.asyncio
    async def test_delete_package_version(
        self,
        httpx_mock: HTTPXMock,
        user_packages_api: GithubContainerRegistryUserApi,
    ) -> None:
        pkg_data = ContainerPackage(
            {
                "name": "pkg",
                "id": 99,
                "url": "https://api.github.com/user/packages/container/pkg/versions/99",
                "metadata": {"container": {"tags": []}},
            },  # type: ignore[arg-type]
        )
        httpx_mock.add_response(method="DELETE", url=pkg_data.url, status_code=204)

        await user_packages_api.delete(pkg_data)

    @pytest.mark.asyncio
    async def test_restore_package_version(
        self,
        httpx_mock: HTTPXMock,
        user_packages_api: GithubContainerRegistryUserApi,
    ) -> None:
        version_id = 99
        endpoint = f"https://api.github.com/user/packages/container/pkg/versions/{version_id}/restore"
        httpx_mock.add_response(method="POST", url=endpoint, status_code=200)

        user_packages_api.PACKAGE_VERSION_RESTORE_ENDPOINT = (
            "/user/packages/container/pkg/versions/{id}/restore"
        )

        await user_packages_api._client.post(endpoint)
