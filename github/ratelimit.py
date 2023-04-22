from datetime import datetime

from github.base import GithubApiBase
from github.base import GithubEndpointResponse


class RateLimits(GithubEndpointResponse):
    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.limit = self._data["rate"]["limit"]
        self.remaining = self._data["rate"]["remaining"]
        self.reset_time = datetime.fromtimestamp(self._data["rate"]["reset"])

    @property
    def limited(self):
        return self.remaining <= 0

    def __str__(self) -> str:
        return f"{self.remaining}/{self.limit} ({self.reset_time})"


class GithubRateLimitApi(GithubApiBase):
    ENDPOINT = "https://api.github.com/rate_limit"

    def limits(self) -> RateLimits:
        resp = self._client.get(self.ENDPOINT)
        resp.raise_for_status()

        return RateLimits(resp.json())
