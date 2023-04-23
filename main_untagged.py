#!/usr/bin/env python3

import logging
from argparse import ArgumentParser

from github.packages import ContainerPackage
from github.packages import GithubContainerRegistryApi
from github.ratelimit import GithubRateLimitApi
from regtools.images import ImageIndexInfo
from regtools.images import check_tag_still_valid
from utils import coerce_to_bool
from utils import get_log_level

logger = logging.getLogger("image-cleaner")


def _main() -> None:
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

    # Get the name of the package owner
    parser.add_argument(
        "--owner",
        help="The owner of the package, either the user or the org",
    )

    # Get the PAT token
    parser.add_argument(
        "--token",
        help="Personal Access Token with the OAuth scope for packages:delete",
    )

    args = parser.parse_args()

    args.delete = coerce_to_bool(args.delete)
    args.is_org = coerce_to_bool(args.is_org)

    logging.basicConfig(
        level=get_log_level(args.loglevel),
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
    with GithubRateLimitApi(args.token) as api:
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
    with GithubContainerRegistryApi(args.token, args.owner, args.is_org) as api:
        # Get the active (not deleted) packages
        active_versions = api.active_versions(args.name)

    # Map the tag (eg latest) to its package and simplify the untagged data
    # mapping name (which is a digest) to the version
    # These just make it easier to do some lookups later
    tag_to_pkgs: dict[str, ContainerPackage] = {}
    untagged_versions = {}
    for pkg in active_versions:
        if pkg.untagged:
            untagged_versions[pkg.name] = pkg
        for tag in pkg.tags:
            tag_to_pkgs[tag] = pkg

    #
    # Step 2 - Find actually untagged packages
    #
    # We're keeping every tag
    tags_to_keep = list(set(tag_to_pkgs.keys()))
    logger.info(f"Keeping {len(tags_to_keep)} for {args.name}")
    for tag in tags_to_keep:
        logger.debug(f"Keeping ghcr.io/{args.owner}/{args.name}:{tag}")

        index_info = ImageIndexInfo(f"ghcr.io/{args.owner}/{args.name}", tag)

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

    #
    # Step 4 - Delete the actually untagged packages
    #
    # Delete the untagged and not pointed at packages
    logger.info(f"Deleting untagged packages of {args.name}")
    if not len(untagged_versions):
        logger.info("Nothing to do")
    with GithubContainerRegistryApi(args.token, args.owner, args.is_org) as api:
        for to_delete_name in untagged_versions:
            to_delete_version = untagged_versions[to_delete_name]

            if args.delete:
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
    logger.info("Beginning confirmation step")
    for tag in tags_to_keep:
        check_tag_still_valid(args.owner, args.name, tag)


if __name__ == "__main__":
    _main()
