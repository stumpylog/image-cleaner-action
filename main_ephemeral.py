#!/usr/bin/env python3

import logging
import re
from argparse import ArgumentParser

from github.branches import GithubBranchApi
from github.packages import ContainerPackage
from github.packages import GithubContainerRegistryApi
from github.pullrequest import GithubPullRequestApi
from github.ratelimit import GithubRateLimitApi
from regtools.images import check_tag_still_valid
from utils import coerce_to_bool
from utils import get_log_level

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


def _get_tags_to_delete_pull_request(
    args: Config,
    matched_packages: list[ContainerPackage],
) -> list[str]:
    """
    Used for a scheme of pull_request.  This method extracts the pull
    request number from the tag and queries for the status of it.  If
    closed, the package is added for deletion
    """
    pkgs_with_closed_pr = []

    with GithubPullRequestApi(args.token) as api:
        for pkg in matched_packages:
            # Don't consider images tagged with more than 1
            if len(pkg.tags) > 1:
                continue
            match = re.match(args.match_regex, pkg.tags[0])
            if match is not None:
                # use the first not None capture group as the PR number
                for x in match.groups():
                    if x is not None:
                        pr_number = int(x)
                        break
                if api.get(args.owner_or_org, args.repo, pr_number).closed:
                    pkgs_with_closed_pr.append(pkg)

    return [x.tags[0] for x in pkgs_with_closed_pr]


def _get_tag_to_delete_branch(
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
    with GithubBranchApi(args.token) as api:
        for branch in api.branches(args.owner_or_org, args.repo):
            if branch.matches(args.match_regex):
                branches_matching_re[branch.name] = branch

    logger.info(f"Found {len(branches_matching_re)} branches to consider")

    return list(set(pkg_tags_to_version.keys()) - set(branches_matching_re.keys()))


def _main() -> None:
    parser = ArgumentParser(
        description="Using the GitHub API locate and optionally delete container"
        " tags which no longer have an associated branch or pull request",
    )

    # Get the PAT token
    parser.add_argument(
        "--token",
        help="Personal Access Token with the OAuth scope for packages:delete",
    )

    # Requires an affirmative command to actually do a delete
    parser.add_argument(
        "--delete",
        default=False,
        help="If provided, actually delete the container tags",
    )

    # Get the name of the package owner
    parser.add_argument(
        "--owner",
        help="The owner of the package, either the user or the org",
    )

    # If true, the owner is an organization
    parser.add_argument(
        "--is-org",
        default=False,
        help="If True, the owner of the package is an organization",
    )

    # Get the name of the package being processed this round
    parser.add_argument(
        "--name",
        help="The package to process",
    )

    # Allows configuration of log level for debugging
    parser.add_argument(
        "--loglevel",
        default="info",
        help="Configures the logging level",
    )

    parser.add_argument(
        "--match-regex",
        help="Regular expression to filter matching image tags",
    )

    parser.add_argument(
        "--repo",
        help="The repository to look at branches or pulls from",
    )

    parser.add_argument(
        "--scheme",
        help="Either 'branch' or 'pull_request', denoting how images are correlated",
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

    with GithubRateLimitApi(config.token) as api:
        current_limits = api.limits()
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
    with GithubContainerRegistryApi(
        config.token,
        config.owner_or_org,
        config.is_org,
    ) as api:
        # Get the active (not deleted) packages
        active_versions = api.active_versions(config.package_name)

    pkgs_matching_re: list[ContainerPackage] = []
    all_pkgs_tags_to_version = {}
    for pkg in active_versions:
        if pkg.untagged:
            continue
        if pkg.tag_matches(config.match_regex):
            pkgs_matching_re.append(pkg)
        for tag in pkg.tags:
            all_pkgs_tags_to_version[tag] = pkg

    if not len(pkgs_matching_re):
        logger.info("No packages to consider")
        return
    else:
        logger.info(f"Found {len(pkgs_matching_re)} packages to consider")

    if config.scheme == "branch":
        tags_to_delete = _get_tag_to_delete_branch(config, pkgs_matching_re)
    elif config.scheme == "pull_request":
        tags_to_delete = _get_tags_to_delete_pull_request(config, pkgs_matching_re)

    tags_to_keep = list(set(all_pkgs_tags_to_version.keys()) - set(tags_to_delete))

    if not len(tags_to_delete):
        logger.info("No images to remove")
        return

    with GithubContainerRegistryApi(
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
                api.delete(
                    to_delete_version,
                )
            else:
                logger.info(
                    f"Would delete {to_delete_name} (id {to_delete_version.id})",
                )

    for tag in tags_to_keep:
        check_tag_still_valid(config.owner_or_org, config.name, tag)


if __name__ == "__main__":
    _main()
