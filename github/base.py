"""
This module contains some useful classes for interacting with the Github API.
The full documentation for the API can be found here: https://docs.github.com/en/rest

Mostly, this focusses on two areas, repo branches and repo packages, as the use case
is cleaning up container images which are no longer referred to.

"""

import asyncio
import builtins
import logging
import re
import time
from http import HTTPStatus
from typing import TypeVar

import github_action_utils as gha_utils
import httpx
from httpx_retries import Retry
from httpx_retries import RetryTransport

logger = logging.getLogger(__name__)

T = TypeVar("T")


class GithubApiBase[T]:
    """
    A base class for interacting with the GitHub API.  It
    will handle the session and setting authorization headers.
    """

    API_BASE_URL = "https://api.github.com"

    def __init__(self, token: str, rate_limit_threshold: int = 100) -> None:
        self._token = token
        self._rate_limit_threshold = rate_limit_threshold
        # Create the client for connection pooling, add headers for type
        # version and authorization
        transport = RetryTransport(
            retry=Retry(
                backoff_factor=0.5,
                status_forcelist=[
                    HTTPStatus.TOO_MANY_REQUESTS,
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    HTTPStatus.BAD_GATEWAY,
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    HTTPStatus.GATEWAY_TIMEOUT,
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

    async def _check_rate_limit(self, response: httpx.Response) -> None:
        """
        Check rate limit headers and sleep if necessary.
        """
        if "X-RateLimit-Remaining" not in response.headers:
            return

        remaining = int(response.headers["X-RateLimit-Remaining"])

        if remaining < self._rate_limit_threshold:
            reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
            if reset_time:
                current_time = int(time.time())
                sleep_duration = max(0, reset_time - current_time + 5)  # Add 5 second buffer

                if sleep_duration > 0:
                    logger.warning(
                        f"Rate limit threshold reached ({remaining} remaining). "
                        f"Sleeping for {sleep_duration} seconds until reset.",
                    )
                    await asyncio.sleep(sleep_duration)

    def _parse_link_header(self, link_header: str) -> dict[str, str]:
        """
        Parse the Link header to extract URLs for pagination.
        Returns a dict like {'next': 'url', 'last': 'url', 'first': 'url', 'prev': 'url'}
        https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api?apiVersion=2022-11-28
        """
        links: dict[str, str] = {}
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

    async def get(self, endpoint: str, query_params: dict | None = None) -> T:
        """
        Get a single resource from the API.
        """
        if query_params is None:
            query_params = {}

        resp = await self._client.get(endpoint, params=query_params)
        await self._check_rate_limit(resp)

        if resp.status_code != HTTPStatus.OK:
            msg = f"Request to {endpoint} returned HTTP {resp.status_code}"
            gha_utils.error(message=msg, title=f"HTTP Error {resp.status_code}")
            logger.error(msg)
            resp.raise_for_status()

        return resp.json()

    async def delete(self, endpoint: str) -> None:
        """
        Delete a resource via the API.
        """
        resp = await self._client.delete(endpoint)
        await self._check_rate_limit(resp)

        if resp.status_code not in (HTTPStatus.NO_CONTENT, HTTPStatus.OK):
            msg = f"Delete request to {endpoint} returned HTTP {resp.status_code}"
            gha_utils.error(message=msg, title=f"HTTP Error {resp.status_code}")
            logger.error(msg)
            resp.raise_for_status()

    async def list(self, endpoint: str, query_params: dict | None = None) -> list[T]:
        """
        List all resources from an endpoint, handling pagination automatically.
        Returns a list of all items across all pages.
        """
        if query_params is None:
            query_params = {}

        # Make the first request to get pagination info
        resp = await self._client.get(endpoint, params=query_params)
        await self._check_rate_limit(resp)

        if resp.status_code != HTTPStatus.OK:
            msg = f"Request to {endpoint} returned HTTP {resp.status_code}"
            gha_utils.error(message=msg, title=f"HTTP Error {resp.status_code}")
            logger.error(msg)
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
        last_page = self._extract_page_number(links.get("last", ""))
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

    async def _fetch_page(self, endpoint: str, params: dict, page_num: int) -> tuple[int, builtins.list[T]]:
        """Fetch a single page and return page number with data"""
        resp = await self._client.get(endpoint, params=params)
        await self._check_rate_limit(resp)

        if resp.status_code != HTTPStatus.OK:
            msg = f"Request to {endpoint} page {page_num} returned HTTP {resp.status_code}"
            logger.error(msg)
            resp.raise_for_status()

        return (page_num, resp.json())


class GithubEndpointResponse:
    """
    For all endpoint JSON responses, store the full
    response data, for ease of extending later, if need be.
    """

    def __init__(self, data: dict) -> None:
        self._data = data
