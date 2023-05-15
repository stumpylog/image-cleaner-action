"""
This module contains some useful classes for interacting with the Github API.
The full documentation for the API can be found here: https://docs.github.com/en/rest

Mostly, this focusses on two areas, repo branches and repo packages, as the use case
is cleaning up container images which are no longer referred to.

"""
import logging
from http import HTTPStatus

import github_action_utils as gha_utils
import httpx

from utils.errors import RateLimitError

logger = logging.getLogger(__name__)


class GithubApiBase:
    """
    A base class for interacting with the GitHub API.  It
    will handle the session and setting authorization headers.
    """

    API_BASE_URL = "https://api.github.com"

    def __init__(self, token: str) -> None:
        self._token = token
        # Create the client for connection pooling, add headers for type
        # version and authorization
        self._client: httpx.Client = httpx.Client(
            base_url=self.API_BASE_URL,
            timeout=30.0,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"token {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Ensures the authorization token is cleaned up no matter
        the reason for the exit
        """
        if "Accept" in self._client.headers:
            del self._client.headers["Accept"]
        if "Authorization" in self._client.headers:
            del self._client.headers["Authorization"]

        # Close the session as well
        self._client.close()
        self._client = None

    def _read_all_pages(self, endpoint: str, query_params: dict | None = None):
        """
        Helper function to read all pages of an endpoint, utilizing the
        next.url until exhausted.  Assumes the endpoint returns a list
        """
        internal_data = []
        if query_params is None:
            query_params = {}

        while True:
            resp = self._client.get(endpoint, params=query_params)
            if resp.status_code == HTTPStatus.OK:
                internal_data += resp.json()
                if "next" in resp.links:
                    endpoint = resp.links["next"]["url"]
                else:
                    logger.debug("Exiting pagination loop")
                    break
            else:
                msg = f"Request to {endpoint} return HTTP {resp.status_code}"
                gha_utils.error(message=msg, title=f"HTTP Error {resp.status_code}")
                logger.error(msg)

                # If forbidden, check if it is rate limiting
                if (
                    resp.status_code == HTTPStatus.FORBIDDEN
                    and "X-RateLimit-Remaining" in resp.headers
                ):
                    remaining = int(resp.headers["X-RateLimit-Remaining"])
                    if remaining <= 0:
                        raise RateLimitError
                resp.raise_for_status()

        return internal_data


class GithubEndpointResponse:
    """
    For all endpoint JSON responses, store the full
    response data, for ease of extending later, if need be.
    """

    def __init__(self, data: dict) -> None:
        self._data = data
