import functools
import logging
import re
import urllib

from github.base import GithubApiBase
from github.base import GithubEndpointResponse

logger = logging.getLogger(__name__)


class ContainerPackage(GithubEndpointResponse):
    """
    Data class wrapping the JSON response from the package related
    endpoints
    """

    def __init__(self, data: dict):
        super().__init__(data)
        # This is a numerical ID, required for interactions with this
        # specific package, including deletion of it or restoration
        self.id: int = self._data["id"]

        # A string name.  This might be an actual name or it could be a
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


class GithubContainerRegistryApi(GithubApiBase):
    """
    Class wrapper to deal with the Github packages API.  This class only deals with
    container type packages, the only type published by paperless-ngx.
    """

    def __init__(self, token: str, owner_or_org: str, is_org: bool = False) -> None:
        super().__init__(token)
        self._owner_or_org = owner_or_org
        self.is_org = is_org
        if self.is_org:
            # https://docs.github.com/en/rest/packages#get-all-package-versions-for-a-package-owned-by-an-organization
            self._PACKAGES_VERSIONS_ENDPOINT = "https://api.github.com/orgs/{ORG}/packages/{PACKAGE_TYPE}/{PACKAGE_NAME}/versions"
            # https://docs.github.com/en/rest/packages#delete-package-version-for-an-organization
            self._PACKAGE_VERSION_DELETE_ENDPOINT = "https://api.github.com/orgs/{ORG}/packages/{PACKAGE_TYPE}/{PACKAGE_NAME}/versions/{PACKAGE_VERSION_ID}"
        else:
            # https://docs.github.com/en/rest/packages#get-all-package-versions-for-a-package-owned-by-the-authenticated-user
            self._PACKAGES_VERSIONS_ENDPOINT = "https://api.github.com/user/packages/{PACKAGE_TYPE}/{PACKAGE_NAME}/versions"
            # https://docs.github.com/en/rest/packages#delete-a-package-version-for-the-authenticated-user
            self._PACKAGE_VERSION_DELETE_ENDPOINT = "https://api.github.com/user/packages/{PACKAGE_TYPE}/{PACKAGE_NAME}/versions/{PACKAGE_VERSION_ID}"
        self._PACKAGE_VERSION_RESTORE_ENDPOINT = (
            f"{self._PACKAGE_VERSION_DELETE_ENDPOINT}/restore"
        )

    def versions(
        self,
        package_name: str,
        active: bool | None = None,
    ) -> list[ContainerPackage]:
        """
        Returns all the versions of a given package (container images) from
        the API with the given state
        """
        package_type: str = "container"
        # Need to quote this for slashes in the name
        package_name = urllib.parse.quote(package_name, safe="")

        endpoint = self._PACKAGES_VERSIONS_ENDPOINT.format(
            ORG=self._owner_or_org,
            PACKAGE_TYPE=package_type,
            PACKAGE_NAME=package_name,
        )
        # Filter to the requested, if any
        if active is not None:
            if active:
                endpoint += "?state=active"
            else:
                endpoint += "?state=deleted"
        # Request the max allowed
        if active is not None:
            endpoint += "&per_page=100"
        else:
            endpoint += "?per_page=100"

        pkgs = []

        for data in self._read_all_pages(endpoint):
            pkgs.append(ContainerPackage(data))

        return pkgs

    def active_versions(
        self,
        package_name: str,
    ) -> list[ContainerPackage]:
        return self.versions(package_name, True)

    def deleted_versions(
        self,
        package_name: str,
    ) -> list[ContainerPackage]:
        return self.versions(package_name, False)

    def delete(self, package_data: ContainerPackage):
        """
        Deletes the given package version from the GHCR
        """
        resp = self._client.delete(package_data.url)
        if resp.status_code != 204:
            logger.warning(
                f"Request to delete {package_data.url} returned HTTP {resp.status_code}",
            )

    def report(
        self,
        package_name: str,
        id: int,
    ):
        package_type: str = "container"
        endpoint = self._PACKAGE_VERSION_RESTORE_ENDPOINT.format(
            ORG=self._owner_or_org,
            PACKAGE_TYPE=package_type,
            PACKAGE_NAME=package_name,
            PACKAGE_VERSION_ID=id,
        )

        resp = self._client.post(endpoint)
        if resp.status_code != 204:
            logger.warning(
                f"Request to delete {endpoint} returned HTTP {resp.status_code}",
            )
