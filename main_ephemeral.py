#!/usr/bin/env python3

import logging
from argparse import ArgumentParser
from pathlib import Path

from github.ratelimit import GithubRateLimitApi
from utils import coerce_to_bool
from utils import get_log_level

logger = logging.getLogger("image-cleaner")


def _main() -> None:
    # Read token for file for now
    # Never checked in
    token = Path("token.txt").read_text().strip()

    parser = ArgumentParser(
        description="Using the GitHub API locate and optionally delete container"
        " tags which no longer have an associated branch or pull request",
    )

    # Requires an affirmative command to actually do a delete
    parser.add_argument(
        "--delete",
        default=False,
        help="If provided, actually delete the container tags",
    )

    parser.add_argument(
        "--regex-str",
        help="Regular expression to filter matching image tags",
    )

    parser.add_argument(
        "--is-org",
        default=False,
        help="If provided, actually delete the container tags",
    )

    # Allows configuration of log level for debugging
    parser.add_argument(
        "--loglevel",
        default="info",
        help="Configures the logging level",
    )

    # Get the name of the package being processed this round
    parser.add_argument(
        "--name",
        help="The package to process",
    )

    args = parser.parse_args()

    args.delete = coerce_to_bool(args.delete)
    args.is_org = coerce_to_bool(args.is_org)

    logging.basicConfig(
        level=get_log_level(args),
        datefmt="%Y-%m-%d %H:%M:%S",
        format="[%(asctime)s] [%(levelname)-8s] [%(name)-10s] %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger.info("Starting processing")

    with GithubRateLimitApi(token) as api:
        current_limits = api.limits()
        if current_limits.limited:
            logger.error(
                f"Currently rate limited, reset at {current_limits.reset_time}",
            )
            return
        else:
            logger.info(f"Rate limits are good: {current_limits}")


if __name__ == "__main__":
    _main()
