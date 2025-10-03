import asyncio
import logging
import os
import re
import time
from collections.abc import AsyncGenerator
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
BUILDX_CACHE_MEDIA_TYPE = "application/vnd.buildkit.cacheconfig.v0"

MANIFEST_MEDIA_TYPES = {
    OCI_INDEX_MEDIA_TYPE,
    DOCKER_MANIFEST_LIST_MEDIA_TYPE,
    OCI_MANIFEST_MEDIA_TYPE,
    DOCKER_MANIFEST_MEDIA_TYPE,
}

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

    def __init__(self, client: httpx.AsyncClient, token: str | None = None) -> None:
        self._tokens: dict[str, CachedToken] = {}
        self._client = client
        self._token = token or os.getenv("GITHUB_TOKEN")

    async def async_auth_flow(
        self,
        request: httpx.Request,
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
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

        token_resp = await self._client.get(
            token_url,
            params={"service": service, "scope": scope},
            headers=headers,
            auth=None,
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
        # Increase the pool timeout as well
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            transport=RetryTransport(
                retry=Retry(
                    total=5,
                    backoff_factor=0.5,
                ),
            ),
            timeout=httpx.Timeout(timeout=15.0, pool=20.0),
            follow_redirects=True,
        )
        self._client.auth = BearerAuth(self._client)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the async context manager and close the client."""
        await self.close()

    async def get_manifest(self, repository: str, reference: str) -> AnyManifest:
        """
        Fetches a manifest or index by tag or digest.

        Args:
            repository: The name of the repository (e.g., 'owner/image').
            reference: The tag or digest (e.g., 'latest' or 'sha256:...').
        """
        manifest_url = f"/v2/{repository}/manifests/{reference}"
        headers = {"Accept": ACCEPT_HEADER}

        logger.debug(f"Requesting manifest: {self.base_url}{manifest_url}")
        resp = await self._client.get(manifest_url, headers=headers)
        resp.raise_for_status()

        parsed_json = resp.json()
        media_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
        if not media_type:
            media_type = parsed_json.get("mediaType", "")

        return get_parsed_type(media_type, parsed_json)

    async def close(self) -> None:
        """Closes the underlying HTTP client."""
        await self._client.aclose()


def format_platform(platform_data: Mapping[str, Any]) -> str:
    """Helper to format platform dictionary into a string."""
    os = platform_data.get("os", "unknown")
    arch = platform_data.get("architecture", "unknown")
    variant = platform_data.get("variant", "")
    return f"{os}/{arch}{variant}"


async def _check_single_tag(
    client,
    repository: str,
    tag: str,
    tag_semaphore: asyncio.Semaphore,
    digest_semaphore: asyncio.Semaphore,
) -> bool:
    """
    Check a single tag:
      - limit concurrent *tag manifest* fetches with `tag_semaphore`
      - limit concurrent *digest* checks with `digest_semaphore` (used when scheduling _check_digest)
    Returns True if the tag and any digests are valid, False otherwise.
    """
    qualified_name = f"{repository}:{tag}"
    try:
        logger.info(f"Checking {qualified_name}")
        # Limit concurrent manifest requests
        async with tag_semaphore:
            root_manifest = await client.get_manifest(repository, tag)

        # If the manifest is an image index / multi-arch, gather manifests from descriptors.
        # Otherwise treat root_manifest itself as the manifest descriptor list of one.
        digest_tasks = []
        if is_multi_arch_media_type(root_manifest):
            manifests = root_manifest.get("manifests", []) or []
            for manifest_descriptor in manifests:
                digest = manifest_descriptor.get("digest")
                media_type = manifest_descriptor.get("mediaType", "")
                if not digest or media_type not in MANIFEST_MEDIA_TYPES:
                    continue
                platform = format_platform(manifest_descriptor.get("platform", {}))
                # schedule digest checks; these calls will themselves use digest_semaphore
                digest_tasks.append(
                    _check_digest_is_valid(client, repository, digest, platform, tag, digest_semaphore),
                )
        else:
            # This is a single-platform image, and we've already fetched it.
            logger.info(f"{qualified_name} is a single-platform image, check successful.")

        # run digest checks (bounded by digest_semaphore inside _check_digest)
        if digest_tasks:
            results = await asyncio.gather(*digest_tasks, return_exceptions=True)
            # Any failure/False => tag considered invalid
            for r in results:
                if isinstance(r, Exception):
                    logger.warning(f"Digest check for {qualified_name} returned exception: {r}")
                    return False
                if r is not True:
                    # r is falsy (False or None) -> treat as invalid
                    return False
        return True

    except Exception as exc:
        logger.exception("Failed checking %s: %s", qualified_name, exc)
        return False


async def _check_digest_is_valid(
    client: RegistryClient,
    repository: str,
    digest: str,
    platform: str,
    tag: str,
    semaphore: asyncio.Semaphore,
) -> bool:
    """
    Checks a single digest manifest.
    Returns True if check failed, False if succeeded.
    """
    async with semaphore:
        digest_name = f"ghcr.io/{repository}@{digest}"
        logger.info(f"Checking digest {digest} for platform {platform} (from {tag})")

        try:
            await client.get_manifest(repository, digest)
            logger.debug(f"Successfully inspected {digest_name}")
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to inspect digest {digest_name}: {e}")
            return False


async def check_tags_still_valid(
    owner: str,
    name: str,
    tags: list[str],
    *,
    tag_concurrency: int = 10,
    digest_concurrency: int = 5,
) -> None:
    """
    Checks if a list of tags and all their referenced image manifests are still valid
    by fetching them directly from the registry API.

    Tags are checked with concurrency limited to 10 requests at a time, with digests limited to 5 at a time
    """
    repository = f"{owner}/{name}"

    async with RegistryClient(host="ghcr.io") as client:
        # Semaphores to bound concurrency
        tag_semaphore = asyncio.BoundedSemaphore(tag_concurrency)
        digest_semaphore = asyncio.BoundedSemaphore(digest_concurrency)

        # Check all tags with limited concurrency
        tag_tasks = [
            _check_single_tag(client, repository, tag, tag_semaphore, digest_semaphore) for tag in tags
        ]
        results = await asyncio.gather(*tag_tasks, return_exceptions=True)

        # Check if any failures occurred
        any_tag_failed = not all(r is True for r in results)

    if any_tag_failed:
        msg = "One or more tags or their digests failed to inspect and may no longer be valid."
        logger.error(msg)
        gha_utils.error(msg, title="Possible registry problems")
        raise Exception(msg)
    else:
        logger.info(f"Successfully verified all tags for {repository} and all their digests.")
