#!/usr/bin/env python3

import logging
import re

import github_action_utils as gha_utils

from github.branches import GithubBranchApi
from github.packages import ContainerPackage
from github.packages import GithubContainerRegistryOrgApi
from github.packages import GithubContainerRegistryUserApi
from github.pullrequest import GithubPullRequestApi
from github.ratelimit import GithubRateLimitApi
from regtools.images import check_tags_still_valid
from utils import coerce_to_bool
from utils import common_args
from utils import get_log_level
from utils.errors import RateLimitError

logger = logging.getLogger("image-cleaner")


class Config:
    def __init__(self, args) -> None:
        self.token: str = args.token
        self.owner_or_org: str = args.owner
        self.is_org = coerce_to_bool(args.is_org)
        self.package_name: str = args.name
        self.log_level: int = get_log_level(args.loglevel)
        self.delete: bool = coerce_to_bool(args.delete)
        self.scheme: str = args.scheme.lower()
        self.repo: str = args.repo
        self.match_regex: str = args.match_regex

        # Validate
        if self.scheme not in {"branch", "pull_request"}:
            raise ValueError(f"{self.scheme} is not a valid option")
        if len(self.match_regex):
            re.compile(self.match_regex)


async def _get_tags_to_delete_pull_request(
    args: Config,
    matched_packages: list[ContainerPackage],
) -> list[str]:
    """
    Used for a scheme of pull_request.  This method extracts the pull
    request number from the tag and queries for the status of it.  If
    closed, the package is added for deletion
    """
    pkgs_with_closed_pr = []

    async with GithubPullRequestApi(args.token) as api:
        for pkg in matched_packages:
            # Don't consider images tagged with more than 1
            # These are more tricky and an owner should evaluate them one by one
            # This only happens sometimes and probably is a mistake, but we shouldn't assume
            if len(pkg.tags) > 1:
                logger.debug(f"Skipping multi-tagged image: {pkg.tags}")
                continue
            match = re.match(args.match_regex, pkg.tags[0])
            pr_number = None
            if match is not None:
                # use the first not None capture group as the PR number
                for x in match.groups():
                    if x is not None:
                        pr_number = int(x)
                        break
                if pr_number and (await api.get(args.owner_or_org, args.repo, pr_number)).closed:
                    pkgs_with_closed_pr.append(pkg)
                elif not pr_number:
                    logger.warning(f"Could not extract PR number from tag {pkg.tags[0]}")
                    continue

    return [x.tags[0] for x in pkgs_with_closed_pr]


async def _get_tag_to_delete_branch(
    args: Config,
    matched_packages: list[ContainerPackage],
) -> list[str]:
    """
    Used for a scheme of branch.  This method associates branches with image
    tags, and returns the set of images which are tagged, but do not have a branch.

    The matched packages must already have filtered out any other tags
    """
    pkg_tags_to_version = {}
    for pkg in matched_packages:
        # Don't consider images tagged with more than 1
        if len(pkg.tags) > 1:
            continue
        for tag in pkg.tags:
            pkg_tags_to_version[tag] = pkg

    logger.info(f"Found {len(pkg_tags_to_version)} tags to consider")

    branches_matching_re = {}
    async with GithubBranchApi(args.token) as api:
        for branch in await api.branches(args.owner_or_org, args.repo):
            if branch.matches(args.match_regex):
                branches_matching_re[branch.name] = branch

    logger.info(f"Found {len(branches_matching_re)} branches to consider")

    return list(set(pkg_tags_to_version.keys()) - set(branches_matching_re.keys()))


async def _main() -> None:
    parser = common_args(
        "Using the GitHub API locate and optionally delete container"
        " tags which no longer have an associated branch or pull request",
    )

    parser.add_argument(
        "--match-regex",
        help="Regular expression to filter matching image tags",
        required=True,
    )

    parser.add_argument(
        "--repo",
        help="The repository to look at branches or pulls from",
        required=True,
    )

    parser.add_argument(
        "--scheme",
        help="Either 'branch' or 'pull_request', denoting how images are correlated",
        required=True,
    )

    config = Config(parser.parse_args())

    logging.basicConfig(
        level=config.log_level,
        datefmt="%Y-%m-%d %H:%M:%S",
        format="[%(asctime)s] [%(levelname)-8s] [%(name)-10s] %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logger.info("Starting processing")

    async with GithubRateLimitApi(config.token) as api:
        current_limits = await api.limits()
        if current_limits.limited:
            logger.error(
                f"Currently rate limited, reset at {current_limits.reset_time}",
            )
            return
        else:
            logger.info(f"Rate limits are good: {current_limits}")

    #
    # Step 1 - gather the active package information
    #
    container_reg_class = GithubContainerRegistryOrgApi if config.is_org else GithubContainerRegistryUserApi
    async with container_reg_class(
        config.token,
        config.owner_or_org,
        config.is_org,
    ) as api:
        logger.info("Getting active packages")
        # Get the active (not deleted) packages
        active_versions = await api.active_versions(config.package_name)
        logger.info(f"{len(active_versions)} active packages")

    #
    # Step 2 - Filter the packages to those which are:
    #            - tagged
    #            - tagged with only 1 thing
    #            - the single tag matches the given regular expression
    #
    pkgs_matching_re: list[ContainerPackage] = []
    all_pkgs_tags_to_version: dict[str, ContainerPackage] = {}
    logger.info("Filtering packages to those matching the regex")
    for pkg in active_versions:
        if pkg.untagged or len(pkg.tags) > 1:
            continue
        if pkg.tag_matches(config.match_regex):
            pkgs_matching_re.append(pkg)
        for tag in pkg.tags:
            all_pkgs_tags_to_version[tag] = pkg

    if not pkgs_matching_re:
        logger.info("No packages to consider")
        return
    else:
        logger.info(f"Found {len(pkgs_matching_re)} packages to consider")

    #
    # Step 3 - Gather the packages to remove (those where the source is gone or closed)
    #
    if config.scheme == "branch":
        logger.info("Looking at branches for deletion considerations")
        tags_to_delete = await _get_tag_to_delete_branch(config, pkgs_matching_re)
    elif config.scheme == "pull_request":
        logger.info("Looking at pull requests for deletion considerations")
        tags_to_delete = await _get_tags_to_delete_pull_request(config, pkgs_matching_re)

    tags_to_keep = list(set(all_pkgs_tags_to_version.keys()) - set(tags_to_delete))

    if not len(tags_to_delete):
        logger.info("No images to remove")
        return
    logger.info(f"Will remove {len(set(tags_to_delete))} tagged packages")
    logger.info(f"Will keep {len(tags_to_keep)} packages")

    #
    # Step 4 - Delete the stale packages
    #
    async with container_reg_class(
        config.token,
        config.owner_or_org,
        config.is_org,
    ) as api:
        for to_delete_name in tags_to_delete:
            to_delete_version = all_pkgs_tags_to_version[to_delete_name]

            if config.delete:
                logger.info(
                    f"Deleting id {to_delete_version.id} named {to_delete_version.name}",
                )
                await api.delete(
                    to_delete_version,
                )
            else:
                logger.info(
                    f"Would delete {to_delete_name} (id {to_delete_version.id})",
                )

    #
    # Step 5 - Be really sure the remaining tags look a-ok
    #
    if config.delete:
        logger.info("Beginning confirmation step")
        await check_tags_still_valid(config.owner_or_org, config.package_name, tags_to_keep)
    else:
        logger.info("Dry run, not checking image manifests")


if __name__ == "__main__":
    import asyncio

    try:
        asyncio.run(_main())
    except RateLimitError:
        logger.error("Rate limit hit during execution")
        gha_utils.error("Rate limit hit during execution")
    finally:
        logging.shutdown()
