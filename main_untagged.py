#!/usr/bin/env python3

import logging
from dataclasses import dataclass

import github_action_utils as gha_utils
import httpx

from github import ContainerPackage
from github import GithubRateLimitApi
from github import create_registry_api
from regtools.images import RegistryClient
from regtools.images import check_tags_still_valid
from regtools.images import format_platform
from regtools.images import is_multi_arch_media_type
from utils import common_args
from utils.config import BaseConfig
from utils.errors import RateLimitError
from utils.logging import setup_logging

logger = logging.getLogger("image-cleaner")


@dataclass(slots=True)
class UntaggedConfig(BaseConfig):
    pass


async def _main() -> None:
    parser = common_args(
        "Using the GitHub API locate and optionally delete container images which are untagged",
    )

    config = UntaggedConfig.from_args(parser.parse_args())

    setup_logging(config.log_level)

    logger.info("Starting processing")

    #
    # Step 0 - Check how the rate limits are looking
    #
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
    async with create_registry_api(config.token, config.owner_or_org, is_org=config.is_org) as api:
        logger.info("Getting active packages")
        # Get the active (not deleted) packages
        active_versions = await api.active_versions(config.package_name)
        logger.info(f"{len(active_versions)} active packages")

    # Map the tag (e.g. latest) to its package and simplify the untagged data
    # mapping name (which is a digest) to the version
    # These just make it easier to do some lookups later
    tag_to_pkgs: dict[str, ContainerPackage] = {}
    untagged_versions: dict[str, ContainerPackage] = {}
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
    logger.info(f"Found {len(tags_to_keep)} tagged images for {config.package_name} which will be kept")
    logger.info("Checking tagged multi-arch images to prevent digest deletion...")
    # TODO: This is a candidate for concurrency using async and probably gather
    async with RegistryClient(host="ghcr.io") as client:
        for tag in tags_to_keep:
            repository = f"{config.owner_or_org}/{config.package_name}"
            qualified_name = f"ghcr.io/{repository}:{tag}"
            logger.debug(f"Checking tag for referenced digests: {qualified_name}")

            try:
                manifest = await client.get_manifest(repository, tag)
            except httpx.HTTPStatusError as e:
                # It's possible a tag in the keep list doesn't exist; log and skip.
                logger.warning(f"Could not fetch manifest for tag '{tag}', skipping. Reason: {e}")
                continue

            # If it's a multi-arch index, check its digests
            if is_multi_arch_media_type(manifest):
                for descriptor in manifest.get("manifests", []):
                    digest = descriptor.get("digest")
                    if digest and digest in untagged_versions:
                        platform = format_platform(descriptor.get("platform", {}))
                        logger.info(
                            f"Keeping digest {digest} for platform {platform} because "
                            f"it is part of tagged image {qualified_name}.",
                        )
                        # This digest is in use, remove it from deletion candidates
                        del untagged_versions[digest]
            else:
                logger.debug(f"{qualified_name} is not multi-arch, nothing to do.")

    if not untagged_versions:
        logger.info("Nothing to do")
        return

    logger.info(
        f"After multi-arch, there are {len(untagged_versions)} untagged packages",
    )

    #
    # Step 3 - Delete the actually untagged packages
    #
    # Delete the untagged and not pointed at packages
    logger.info(f"Deleting untagged packages of {config.package_name}")
    async with create_registry_api(config.token, config.owner_or_org, is_org=config.is_org) as api:
        for to_delete_name, to_delete_version in untagged_versions.items():
            if config.delete:
                logger.info(
                    f"Deleting id {to_delete_version.id} named {to_delete_version.name}",
                )
                await api.delete_package(
                    to_delete_version,
                )
            else:
                logger.info(
                    f"Would delete {to_delete_name} (id {to_delete_version.id})",
                )

    #
    # Step 4 - Be really sure the remaining tags look a-ok
    #
    if config.delete:
        logger.info("Beginning confirmation step")
        await check_tags_still_valid(config.owner_or_org, config.package_name, tags_to_keep)
    else:
        logger.info("Dry run, not checking images")


if __name__ == "__main__":
    import asyncio

    try:
        asyncio.run(_main())
    except RateLimitError:
        logger.error("Rate limit hit during execution")
        gha_utils.error("Rate limit hit during execution")
    finally:
        logging.shutdown()
