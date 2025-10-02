"""
This module contains some useful classes for interacting with the Github API.
The full documentation for the API can be found here: https://docs.github.com/en/rest

Mostly, this focusses on two areas, repo branches and repo packages, as the use case
is cleaning up container images which are no longer referred to.

"""

import asyncio
import logging
import re
from http import HTTPStatus

import github_action_utils as gha_utils
import httpx
from httpx_retries import Retry
from httpx_retries import RetryTransport

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
        self._client: httpx.AsyncClient = httpx.AsyncClient(
            http2=True,
            base_url=self.API_BASE_URL,
            timeout=30.0,
            transport=transport,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"token {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Ensures the authorization token is cleaned up no matter
        the reason for the exit
        """
        if "Accept" in self._client.headers:
            del self._client.headers["Accept"]
        if "Authorization" in self._client.headers:
            del self._client.headers["Authorization"]

        # Close the session as well
        await self._client.aclose()

    def _parse_link_header(self, link_header: str) -> dict[str, str]:
        """
        Parse the Link header to extract URLs for pagination.
        Returns a dict like {'next': 'url', 'last': 'url', 'first': 'url', 'prev': 'url'}
        """
        links = {}
        if not link_header:
            return links

        for link in link_header.split(","):
            parts = link.strip().split(";")
            if len(parts) != 2:
                continue
            url = parts[0].strip("<> ")
            rel_match = re.search(r'rel="(\w+)"', parts[1])
            if rel_match:
                links[rel_match.group(1)] = url

        return links

    def _extract_page_number(self, url: str) -> int | None:
        """Extract page number from a GitHub API URL"""
        match = re.search(r"[?&]page=(\d+)", url)
        return int(match.group(1)) if match else None

    async def _read_all_pages(self, endpoint: str, query_params: dict | None = None):
        """
        Helper function to read all pages of an endpoint, utilizing the
        next.url until exhausted.  Assumes the endpoint returns a list.
        """
        if query_params is None:
            query_params = {}

        # Make the first request to get pagination info
        resp = await self._client.get(endpoint, params=query_params)

        if resp.status_code != HTTPStatus.OK:
            msg = f"Request to {endpoint} return HTTP {resp.status_code}"
            gha_utils.error(message=msg, title=f"HTTP Error {resp.status_code}")
            logger.error(msg)

            # If forbidden, check if it is rate limiting
            if resp.status_code == HTTPStatus.FORBIDDEN and "X-RateLimit-Remaining" in resp.headers:
                remaining = int(resp.headers["X-RateLimit-Remaining"])
                if remaining <= 0:
                    raise RateLimitError
            resp.raise_for_status()

        # Store first page data
        all_data = {1: resp.json()}

        # Check if there are more pages
        link_header = resp.headers.get("Link", "")
        if not link_header:
            # Only one page
            return all_data[1]

        links = self._parse_link_header(link_header)

        # Extract total number of pages
        last_page = self._extract_page_number(links["last"])
        if not last_page or last_page == 1:
            return all_data[1]

        logger.debug(f"Found {last_page} total pages, fetching pages 2-{last_page} concurrently")

        # Create tasks for remaining pages
        tasks = []
        for page in range(2, last_page + 1):
            page_params = {**query_params, "page": page}
            tasks.append(self._fetch_page(endpoint, page_params, page))

        # Fetch all pages concurrently with a semaphore to limit concurrency
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests

        async def fetch_with_semaphore(task):
            async with semaphore:
                return await task

        results = await asyncio.gather(*[fetch_with_semaphore(task) for task in tasks])

        # Add results to our data dict
        for page_num, page_data in results:
            all_data[page_num] = page_data

        # Combine all pages in order
        combined_data = []
        for page in sorted(all_data.keys()):
            combined_data.extend(all_data[page])

        return combined_data

    async def _fetch_page(self, endpoint: str, params: dict, page_num: int) -> tuple[int, list]:
        """Fetch a single page and return page number with data"""
        resp = await self._client.get(endpoint, params=params)

        if resp.status_code != HTTPStatus.OK:
            msg = f"Request to {endpoint} page {page_num} returned HTTP {resp.status_code}"
            logger.error(msg)

            if resp.status_code == HTTPStatus.FORBIDDEN and "X-RateLimit-Remaining" in resp.headers:
                remaining = int(resp.headers["X-RateLimit-Remaining"])
                if remaining <= 0:
                    raise RateLimitError
            resp.raise_for_status()

        return (page_num, resp.json())


class GithubEndpointResponse:
    """
    For all endpoint JSON responses, store the full
    response data, for ease of extending later, if need be.
    """

    def __init__(self, data: dict) -> None:
        self._data = data
