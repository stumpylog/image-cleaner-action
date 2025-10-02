import logging
import os
import re
import time
from collections.abc import Generator
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from typing import Self
from typing import TypeGuard
from typing import cast

import github_action_utils as gha_utils
import httpx
from httpx_retries import Retry
from httpx_retries import RetryTransport

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

AnyManifest = OCIImageIndex | DockerManifestList | OCIManifest | DockerManifestV2
AnyIndex = OCIImageIndex | DockerManifestList


def get_parsed_type(media_type: str, parsed_json: dict[str, Any]) -> AnyManifest:
    """
    Casts a parsed JSON dict to the correct TypedDict model based on mediaType.
    """
    if media_type == OCI_INDEX_MEDIA_TYPE:
        return cast(OCIImageIndex, parsed_json)
    if media_type == DOCKER_MANIFEST_LIST_MEDIA_TYPE:
        return cast(DockerManifestList, parsed_json)
    if media_type == OCI_MANIFEST_MEDIA_TYPE:
        return cast(OCIManifest, parsed_json)
    if media_type == DOCKER_MANIFEST_MEDIA_TYPE:
        return cast(DockerManifestV2, parsed_json)

    raise ValueError(f"Unknown media type: {media_type}")


def is_multi_arch_media_type(data: AnyManifest) -> TypeGuard[AnyIndex]:
    """
    Type guard to narrow AnyManifest to AnyIndex (multi-arch types).
    """
    return data.get("mediaType", "") in {OCI_INDEX_MEDIA_TYPE, DOCKER_MANIFEST_LIST_MEDIA_TYPE}


@dataclass(frozen=True, slots=True)
class CachedToken:
    """
    A cached bearer token with expiration tracking.
    """

    token: str
    expires_at: float


class BearerAuth(httpx.Auth):
    """
    Custom authentication handler for httpx to manage registry bearer tokens.
    It automatically fetches and caches tokens based on the repository scope,
    with expiration tracking to avoid using stale tokens.
    """

    __slots__ = ("_client", "_token", "_tokens")

    def __init__(self, client: httpx.Client, token: str | None = None) -> None:
        self._tokens: dict[str, CachedToken] = {}
        self._client = client
        self._token = token or os.getenv("GITHUB_TOKEN")

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """
        Handles the full authentication flow, including token acquisition.
        """
        # Extract the repository from the URL
        repo_match = re.search(r"/v2/(.+?)/(manifests|blobs)/", request.url.path)
        if not repo_match:
            raise ValueError(f"Could not determine repository from URL: {request.url.path}")

        scope = f"repository:{repo_match.group(1)}:pull"

        # Check if we have a valid cached token for this scope
        if (cached := self._tokens.get(scope)) and time.time() < cached.expires_at:
            request.headers["Authorization"] = f"Bearer {cached.token}"
            yield request
            return

        # Try the request unauthenticated first to get the auth challenge
        response: httpx.Response = yield request

        if response.status_code != httpx.codes.UNAUTHORIZED or "Www-Authenticate" not in response.headers:
            return

        # Parse the authentication challenge
        auth_header = response.headers["Www-Authenticate"]
        realm_match = re.search(r'Bearer realm="([^"]+)"', auth_header)
        service_match = re.search(r'service="([^"]+)"', auth_header)

        if not realm_match or not service_match:
            raise ValueError("Invalid Www-Authenticate header")

        token_url = realm_match.group(1)
        service = service_match.group(1)

        # Request a new token - use PAT as Bearer if available
        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        token_resp = self._client.get(
            token_url,
            params={"service": service, "scope": scope},
            headers=headers,
        )
        token_resp.raise_for_status()

        token_data = token_resp.json()
        if "token" not in token_data:
            raise ValueError(f"Token response missing 'token' field: {token_data}")

        new_token = token_data["token"]
        # GHCR tokens typically expire in 300 seconds (5 minutes)
        # Use a 30 second buffer to avoid edge cases
        expires_in = token_data.get("expires_in", 300)
        expires_at = time.time() + expires_in - 30

        # Cache the token and retry the original request
        self._tokens[scope] = CachedToken(token=new_token, expires_at=expires_at)
        request.headers["Authorization"] = f"Bearer {new_token}"
        yield request


class RegistryClient:
    """A client for interacting with an OCI container registry via HTTP."""

    def __init__(self, host: str = "ghcr.io") -> None:
        self.host = host
        self.base_url = f"https://{self.host}"
        # Use a transport with retries for network resilience
        transport = RetryTransport(
            retry=Retry(
                backoff_factor=0.5,
                status_forcelist=[
                    httpx.codes.TOO_MANY_REQUESTS,  # 429
                    httpx.codes.INTERNAL_SERVER_ERROR,  # 500
                    httpx.codes.BAD_GATEWAY,  # 502
                    httpx.codes.SERVICE_UNAVAILABLE,  # 503
                    httpx.codes.GATEWAY_TIMEOUT,  # 504
                ],
            ),
        )
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


def check_tags_still_valid(owner: str, name: str, tags: list[str]) -> None:
    """
    Checks if a list of tags and all their referenced image manifests are still valid
    by fetching them directly from the registry API.
    """
    repository = f"{owner}/{name}"
    any_tag_failed = False

    with RegistryClient(host="ghcr.io") as client:
        for tag in tags:
            qualified_name = f"ghcr.io/{repository}:{tag}"
            try:
                logger.info(f"Checking {qualified_name}")
                root_manifest = client.get_manifest(repository, tag)

                # Check if the root manifest is an image index (multi-arch)
                if is_multi_arch_media_type(root_manifest):
                    logger.info(f"{qualified_name} is a multi-arch image index.")

                    for manifest_descriptor in root_manifest.get("manifests", []):
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
                            any_tag_failed = True
                            logger.error(f"Failed to inspect digest {digest_name}: {e}")
                else:
                    # This is a single-platform image, and we've already fetched it.
                    logger.info(f"{qualified_name} is a single-platform image, check successful.")

            except httpx.HTTPError as e:
                any_tag_failed = True
                logger.error(f"Failed to inspect initial tag {qualified_name}: {e}")
                gha_utils.error(
                    message=f"Tag {qualified_name} failed to inspect and may no longer be valid.",
                    title=f"Verification failure: {qualified_name}",
                )

    if any_tag_failed:
        msg = "One or more tags or their digests failed to inspect and may no longer be valid."
        raise Exception(msg)
    else:
        logger.info(f"Successfully verified all tags for {repository} and all their digests.")
