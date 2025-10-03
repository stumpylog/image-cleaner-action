from datetime import datetime

from github.base import GithubApiBase
from github.base import GithubEndpointResponse
from github.models.ratelimit import RateLimitOverview


class RateLimits(GithubEndpointResponse[RateLimitOverview]):
    def __init__(self, data: RateLimitOverview) -> None:
        super().__init__(data)  # type: ignore[arg-type]
        self.limit = self._data["rate"]["limit"]
        self.remaining = self._data["rate"]["remaining"]
        self.reset_time = datetime.fromtimestamp(self._data["rate"]["reset"])

    @property
    def limited(self) -> bool:
        return self.remaining <= 0

    def __str__(self) -> str:
        return f"{self.remaining}/{self.limit} (reset @ {self.reset_time})"


class GithubRateLimitApi(GithubApiBase[RateLimitOverview]):
    ENDPOINT = "https://api.github.com/rate_limit"

    async def limits(self) -> RateLimits:
        return RateLimits(await self.get(self.ENDPOINT))
