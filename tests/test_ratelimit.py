from datetime import datetime

import pytest

from github.ratelimit import GithubRateLimitApi
from github.ratelimit import RateLimits


class TestGithubRateLimitApi:
    @pytest.mark.asyncio
    async def test_limits(self, httpx_mock, ratelimit_api: GithubRateLimitApi):
        response_json = {
            "rate": {
                "limit": 5000,
                "remaining": 4999,
                "reset": 1234567890,
            },
        }
        httpx_mock.add_response(json=response_json)
        limits = await ratelimit_api.limits()
        assert isinstance(limits, RateLimits)
        assert not limits.limited
        assert limits.remaining == 4999
        assert limits.reset_time == datetime.fromtimestamp(1234567890)
