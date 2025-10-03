import functools
import logging
import re
import urllib.parse
from http import HTTPStatus
from typing import TypeVar

import github_action_utils as gha_utils

from github.base import GithubApiBase
from github.base import GithubEndpointResponse
from github.models.packages.organization import Package as OrgPackage
from github.models.packages.user import Package as UserPackage
from utils.errors import RateLimitError

logger = logging.getLogger(__name__)
T = TypeVar("T")


class ContainerPackage(GithubEndpointResponse):
    """
    Data class wrapping the JSON response from the package related
    endpoints
    """

    def __init__(self, data: UserPackage | OrgPackage):
        super().__init__(data)  # type: ignore[arg-type]
        # This is a numerical ID, required for interactions with this
        # specific package, including deletion of it or restoration
        self.id: int = self._data["id"]

        # A string name.  This might be an actual name, or it could be a
        # digest string like "sha256:"
        self.name: str = self._data["name"]

        # URL to the package, including its ID, can be used for deletion
        # or restoration without needing to build up a URL ourselves
        self.url: str = self._data["url"]

        # The list of tags applied to this image. Maybe an empty list
        self.tags: list[str] = self._data["metadata"]["container"]["tags"]

    @functools.cached_property
    def untagged(self) -> bool:
        """
        Returns True if the image has no tags applied to it, False otherwise
        """
        return len(self.tags) == 0

    @functools.cached_property
    def tagged(self) -> bool:
        """
        Returns True if the image has tags applied to it, False otherwise
        """
        return not self.untagged

    @functools.lru_cache
    def tag_matches(self, pattern: str) -> bool:
        """
        Returns True if the image has at least one tag which matches the given regex,
        False otherwise
        """
        return any(re.match(pattern, tag) is not None for tag in self.tags)

    def __str__(self):
        return f"Package {self.name}"


class _GithubContainerRegistryApiBase[T](GithubApiBase[T]):
    PACKAGE_VERSIONS_ENDPOINT: str = ""
    PACKAGE_VERSION_DELETE_ENDPOINT: str = ""
    PACKAGE_VERSION_RESTORE_ENDPOINT: str = ""

    def __init__(self, token: str, owner_or_org: str, is_org: bool = False) -> None:
        super().__init__(token)
        self._owner_or_org = owner_or_org
        self.is_org = is_org

    async def versions(
        self,
        package_name: str,
        *,
        active: bool | None = None,
    ) -> list[ContainerPackage]:
        """
        Returns all the versions of a given package (container images) from
        the API with the given state
        """
        package_type: str = "container"
        # Need to quote this for slashes in the name
        package_name = urllib.parse.quote(package_name, safe="")

        endpoint = self.PACKAGE_VERSIONS_ENDPOINT.format(
            ORG=self._owner_or_org,
            PACKAGE_TYPE=package_type,
            PACKAGE_NAME=package_name,
        )

        # Always request the max allowed per page
        query_params: dict[str, str | int] = {"per_page": 100}

        # Filter to the requested state, if any
        if active is not None:
            if active:
                query_params["state"] = "active"
            else:
                query_params["state"] = "deleted"

        pkgs = []

        for data in await self.list(endpoint, query_params=query_params):
            pkgs.append(ContainerPackage(data))  # type: ignore[arg-type]

        return pkgs

    async def active_versions(
        self,
        package_name: str,
    ) -> list[ContainerPackage]:
        return await self.versions(package_name, active=True)

    async def deleted_versions(
        self,
        package_name: str,
    ) -> list[ContainerPackage]:
        return await self.versions(package_name, active=False)

    async def delete_package(self, package_data: ContainerPackage):
        """
        Deletes the given package version from the GHCR
        """
        await self.delete(package_data.url)

    async def restore(
        self,
        package_name: str,
        id: int,
    ):
        package_type: str = "container"
        endpoint = self.PACKAGE_VERSION_RESTORE_ENDPOINT.format(
            ORG=self._owner_or_org,
            PACKAGE_TYPE=package_type,
            PACKAGE_NAME=package_name,
            PACKAGE_VERSION_ID=id,
        )

        resp = await self._client.post(endpoint)
        if resp.status_code != HTTPStatus.NO_CONTENT:
            # If forbidden, check if it is rate limiting
            if resp.status_code == HTTPStatus.FORBIDDEN and "X-RateLimit-Remaining" in resp.headers:
                remaining = int(resp.headers["X-RateLimit-Remaining"])
                if remaining <= 0:
                    raise RateLimitError
            else:
                msg = f"Request to restore id {id} returned HTTP {resp.status_code}"
                gha_utils.warning(
                    message=msg,
                    title=f"Unexpected restore status: {resp.status_code}",
                )
                logger.warning(msg)


class GithubContainerRegistryOrgApi(_GithubContainerRegistryApiBase[OrgPackage]):
    """
    Class wrapper to deal with the GitHub packages API.  This class only deals with
    container type packages.
    This class is for organizations
    """

    PACKAGE_VERSIONS_ENDPOINT = "/orgs/{ORG}/packages/{PACKAGE_TYPE}/{PACKAGE_NAME}/versions"
    PACKAGE_VERSION_DELETE_ENDPOINT = (
        "/orgs/{ORG}/packages/{PACKAGE_TYPE}/{PACKAGE_NAME}/versions/{PACKAGE_VERSION_ID}"
    )
    PACKAGE_VERSION_RESTORE_ENDPOINT = (
        "/orgs/{ORG}/packages/{PACKAGE_TYPE}/{PACKAGE_NAME}/versions/{PACKAGE_VERSION_ID}/restore"
    )


class GithubContainerRegistryUserApi(_GithubContainerRegistryApiBase[UserPackage]):
    """
    Class wrapper to deal with the GitHub packages API.  This class only deals with
    container type packages.
    This class is for user owned packages
    """

    PACKAGE_VERSIONS_ENDPOINT = "/user/packages/{PACKAGE_TYPE}/{PACKAGE_NAME}/versions"
    PACKAGE_VERSION_DELETE_ENDPOINT = (
        "/user/packages/{PACKAGE_TYPE}/{PACKAGE_NAME}/versions/{PACKAGE_VERSION_ID}"
    )
    PACKAGE_VERSION_RESTORE_ENDPOINT = (
        "/user/packages/{PACKAGE_TYPE}/{PACKAGE_NAME}/versions/{PACKAGE_VERSION_ID}/restore"
    )
