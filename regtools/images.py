import logging
import os
import re
from collections.abc import Iterator
from collections.abc import Mapping
from typing import TYPE_CHECKING
from typing import Any
from typing import Self
from typing import cast

import github_action_utils as gha_utils
import httpx

# Assuming models.py is in the same directory or accessible in the python path
from regtools.models import DockerManifestList
from regtools.models import DockerManifestV2
from regtools.models import OCIImageIndex
from regtools.models import OCIManifest

# Constants for media types and the HTTP Accept header
OCI_INDEX_MEDIA_TYPE = "application/vnd.oci.image.index.v1+json"
DOCKER_MANIFEST_LIST_MEDIA_TYPE = "application/vnd.docker.distribution.manifest.list.v2+json"
OCI_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
DOCKER_MANIFEST_MEDIA_TYPE = "application/vnd.docker.distribution.manifest.v2+json"

ACCEPT_HEADER = (
    f"{OCI_INDEX_MEDIA_TYPE}, "
    f"{DOCKER_MANIFEST_LIST_MEDIA_TYPE}, "
    f"{OCI_MANIFEST_MEDIA_TYPE}, "
    f"{DOCKER_MANIFEST_MEDIA_TYPE}"
)

logger = logging.getLogger(__name__)

# --- Type Aliases ---
AnyManifest = OCIImageIndex | DockerManifestList | OCIManifest | DockerManifestV2
AnyIndex = OCIImageIndex | DockerManifestList


def get_parsed_type(media_type: str, parsed_json: dict[str, Any]) -> AnyManifest:
    """Casts a parsed JSON dict to the correct TypedDict model based on mediaType."""
    if media_type == OCI_INDEX_MEDIA_TYPE:
        return cast(OCIImageIndex, parsed_json)
    if media_type == DOCKER_MANIFEST_LIST_MEDIA_TYPE:
        return cast(DockerManifestList, parsed_json)
    if media_type == OCI_MANIFEST_MEDIA_TYPE:
        return cast(OCIManifest, parsed_json)
    if media_type == DOCKER_MANIFEST_MEDIA_TYPE:
        return cast(DockerManifestV2, parsed_json)

    raise ValueError(f"Unknown media type: {media_type}")


def is_multi_arch_media_type(data: AnyManifest) -> bool:
    return data.get("mediaType", "") in {OCI_INDEX_MEDIA_TYPE, DOCKER_MANIFEST_LIST_MEDIA_TYPE}


class BearerAuth(httpx.Auth):
    """
    Custom authentication handler for httpx to manage registry bearer tokens.
    It automatically fetches and caches tokens based on the repository scope.
    """

    def __init__(self, client: httpx.Client) -> None:
        self._tokens: dict[str, str] = {}
        self._client = client
        # For GHCR, auth requires a username, which can be the GITHUB_TOKEN owner
        # or a placeholder like 'x-access-token' when using a PAT.
        self._user = os.getenv("GITHUB_ACTOR", "x-access-token")
        self._password = os.getenv("GITHUB_TOKEN")

    def auth_flow(self, request: httpx.Request) -> Iterator[httpx.Request]:
        """Handles the full authentication flow, including token acquisition."""
        # Extract the repository from the URL, e.g., 'v2/owner/repo/manifests/tag'
        repo_match = re.search(r"/v2/([^/]+/[^/]+)/", request.url.path)
        if not repo_match:
            raise ValueError("Could not determine repository from URL")
        scope = f"repository:{repo_match.group(1)}:pull"

        # If we have a token for this scope, use it
        if token := self._tokens.get(scope):
            request.headers["Authorization"] = f"Bearer {token}"
            yield request
            return

        # Try the request unauthenticated first to get the 'Www-Authenticate' header
        response = yield request
        if response.status_code != 401 or "Www-Authenticate" not in response.headers:
            return  # Not an auth challenge, let the client handle it

        # Parse the 'Www-Authenticate' header to find the token service URL
        auth_header = response.headers["Www-Authenticate"]
        realm_match = re.search(r'Bearer realm="([^"]+)"', auth_header)
        service_match = re.search(r'service="([^"]+)"', auth_header)

        if not realm_match or not service_match:
            raise ValueError("Invalid Www-Authenticate header")

        token_url = realm_match.group(1)
        service = service_match.group(1)

        # Request a new token from the authentication service
        auth = (self._user, self._password) if self._password else None
        token_resp = self._client.get(
            token_url,
            params={"service": service, "scope": scope},
            auth=auth,
        )
        token_resp.raise_for_status()
        new_token = token_resp.json()["token"]

        # Cache the token and retry the original request
        self._tokens[scope] = new_token
        request.headers["Authorization"] = f"Bearer {new_token}"
        yield request


class RegistryClient:
    """A client for interacting with an OCI container registry via HTTP."""

    def __init__(self, host: str = "ghcr.io") -> None:
        self.host = host
        self.base_url = f"https://{self.host}"
        # Use a transport with retries for network resilience
        transport = httpx.HTTPTransport(retries=4)
        self._client = httpx.Client(
            base_url=self.base_url,
            transport=transport,
            follow_redirects=True,
        )
        self._client.auth = BearerAuth(self._client)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context manager and close the client."""
        self.close()

    def get_manifest(self, repository: str, reference: str) -> AnyManifest:
        """
        Fetches a manifest or index by tag or digest.

        Args:
            repository: The name of the repository (e.g., 'owner/image').
            reference: The tag or digest (e.g., 'latest' or 'sha256:...').
        """
        manifest_url = f"/v2/{repository}/manifests/{reference}"
        headers = {"Accept": ACCEPT_HEADER}

        logger.debug(f"Requesting manifest: {self.base_url}{manifest_url}")
        resp = self._client.get(manifest_url, headers=headers)
        resp.raise_for_status()

        parsed_json = resp.json()
        media_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
        if not media_type:
            media_type = parsed_json.get("mediaType", "")

        return get_parsed_type(media_type, parsed_json)

    def close(self) -> None:
        """Closes the underlying HTTP client."""
        self._client.close()


def format_platform(platform_data: Mapping[str, Any]) -> str:
    """Helper to format platform dictionary into a string."""
    os = platform_data.get("os", "unknown")
    arch = platform_data.get("architecture", "unknown")
    variant = platform_data.get("variant", "")
    return f"{os}/{arch}{variant}"


def check_tag_still_valid(owner: str, name: str, tag: str) -> None:
    """
    Checks if a tag and all its referenced image manifests are still valid
    by fetching them directly from the registry API.
    """
    repository = f"{owner}/{name}"
    qualified_name = f"ghcr.io/{repository}:{tag}"
    a_tag_failed = False

    try:
        with RegistryClient(host="ghcr.io") as client:
            logger.info(f"Checking {qualified_name}")
            root_manifest = client.get_manifest(repository, tag)

            # Check if the root manifest is an image index (multi-arch)
            if is_multi_arch_media_type(root_manifest):
                if TYPE_CHECKING:
                    root_manifest: OCIImageIndex | DockerManifestList
                logger.info(f"{qualified_name} is a multi-arch image index.")
                for manifest_descriptor in root_manifest["manifests"]:
                    digest = manifest_descriptor.get("digest")
                    if not digest:
                        continue
                    platform = format_platform(manifest_descriptor.get("platform", {}))
                    digest_name = f"ghcr.io/{repository}@{digest}"
                    logger.info(f"Checking digest {digest} for platform {platform}")

                    try:
                        client.get_manifest(repository, digest)
                        logger.debug(f"Successfully inspected {digest_name}")
                    except httpx.HTTPError as e:
                        a_tag_failed = True
                        logger.error(f"Failed to inspect digest {digest_name}: {e}")
            else:
                # This is a single-platform image, and we've already fetched it.
                logger.info(f"{qualified_name} is a single-platform image, check successful.")

    except httpx.HTTPError as e:
        a_tag_failed = True
        logger.error(f"Failed to inspect initial tag {qualified_name}: {e}")

    if a_tag_failed:
        msg = f"Tag {qualified_name} or one of its digests failed to inspect and may no longer be valid."
        gha_utils.error(
            message=msg,
            title=f"Verification failure: {qualified_name}",
        )
        raise Exception(msg)
    else:
        logger.info(f"Successfully verified tag {qualified_name} and all its digests.")
