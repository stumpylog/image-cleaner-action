#!/usr/bin/env python3

import logging

import github_action_utils as gha_utils

from github.packages import ContainerPackage
from github.packages import GithubContainerRegistryOrgApi
from github.packages import GithubContainerRegistryUserApi
from github.ratelimit import GithubRateLimitApi
from regtools.images import ImageIndexInfo
from regtools.images import check_tag_still_valid
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


def _main() -> None:
    parser = common_args(
        "Using the GitHub API locate and optionally delete container"
        "images which are untagged",
    )

    config = Config(parser.parse_args())

    logging.basicConfig(
        level=config.log_level,
        datefmt="%Y-%m-%d %H:%M:%S",
        format="[%(asctime)s] [%(levelname)-8s] [%(name)-10s] %(message)s",
    )
    # https likes to log at INFO, reduce that
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logger.info("Starting processing")

    #
    # Step 0 - Check how the rate limits are looking
    #
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
    container_reg_class = (
        GithubContainerRegistryOrgApi
        if config.is_org
        else GithubContainerRegistryUserApi
    )
    with container_reg_class(
        config.token,
        config.owner_or_org,
        config.is_org,
    ) as api:
        logger.info("Getting active packages")
        # Get the active (not deleted) packages
        active_versions = api.active_versions(config.package_name)
        logger.info(f"{len(active_versions)} active packages")

    # Map the tag (e.g. latest) to its package and simplify the untagged data
    # mapping name (which is a digest) to the version
    # These just make it easier to do some lookups later
    tag_to_pkgs: dict[str, ContainerPackage] = {}
    untagged_versions = {}
    for pkg in active_versions:
        if pkg.untagged:
            untagged_versions[pkg.name] = pkg
        for tag in pkg.tags:
            tag_to_pkgs[tag] = pkg

    logger.info(f"Found {len(untagged_versions)} packages which look untagged")

    #
    # Step 2 - Find actually untagged packages
    #
    # We're keeping every tag
    tags_to_keep = list(set(tag_to_pkgs.keys()))
    logger.info(f"Keeping {len(tags_to_keep)} for {config.package_name}")
    for tag in tags_to_keep:
        logger.debug(
            f"Keeping ghcr.io/{config.owner_or_org}/{config.package_name}:{tag}",
        )

        index_info = ImageIndexInfo(
            f"ghcr.io/{config.owner_or_org}/{config.package_name}",
            tag,
        )

        # These are not pointers.  If untagged, it's actually untagged
        if not index_info.is_multi_arch:
            logger.info(
                f"{index_info.qualified_name} is not multi-arch, nothing to do",
            )
            continue

        for manifest in index_info.image_pointers:
            if manifest.digest in untagged_versions:
                logger.info(
                    f"Skipping deletion of {manifest.digest},"
                    f" referred to by {index_info.qualified_name}"
                    f" for {manifest.platform}",
                )
                del untagged_versions[manifest.digest]

            # TODO Make it clear for digests which are multi-tagged (latest, x.x.y)
            # they are not being deleted too

    if not len(untagged_versions):
        logger.info("Nothing to do")
        return

    logger.info(
        f"After multi-arch, there are {len(untagged_versions)} untagged packages",
    )

    #
    # Step 4 - Delete the actually untagged packages
    #
    # Delete the untagged and not pointed at packages
    logger.info(f"Deleting untagged packages of {config.package_name}")
    with container_reg_class(
        config.token,
        config.owner_or_org,
        config.is_org,
    ) as api:
        for to_delete_name in untagged_versions:
            to_delete_version = untagged_versions[to_delete_name]

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

    #
    # Step 5 - Be really sure the remaining tags look a-ok
    #
    if config.delete:
        logger.info("Beginning confirmation step")
        for tag in tags_to_keep:
            check_tag_still_valid(config.owner_or_org, config.package_name, tag)
    else:
        logger.info("Dry run, not checking images")


if __name__ == "__main__":
    try:
        _main()
    except RateLimitError:
        logger.error("Rate limit hit during execution")
        gha_utils.error("Rate limit hit during execution")
    finally:
        logging.shutdown()
