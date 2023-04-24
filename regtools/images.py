import functools
import json
import logging
import shutil
import subprocess
import time
from collections.abc import Iterator

logger = logging.getLogger(__name__)


class BaseImageProperties:
    def __init__(self, data: dict) -> None:
        self._data = data


class MultiArchImageProperties(BaseImageProperties):
    """
    Data class wrapping the properties of an entry in the image index
    manifests list.  It is NOT an actual image with layers, etc

    https://docs.docker.com/registry/spec/manifest-v2-2/
    https://github.com/opencontainers/image-spec/blob/main/manifest.md
    https://github.com/opencontainers/image-spec/blob/main/descriptor.md
    """

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        # This is the sha256: digest string.  Corresponds to GitHub API name
        # if the package is an untagged package
        self.digest = self._data["digest"]
        platform_data_os = self._data["platform"]["os"]
        platform_arch = self._data["platform"]["architecture"]
        platform_variant = self._data["platform"].get(
            "variant",
            "",
        )
        self.platform = f"{platform_data_os}/{platform_arch}{platform_variant}"


class ImageIndexInfo:
    """
    Data class wrapping up logic for an OCI Image Index
    JSON data.  Primary use is to access the manifests listing

    See https://github.com/opencontainers/image-spec/blob/main/image-index.md
    """

    def __init__(self, package_url: str, tag: str) -> None:
        self._data = None
        self.qualified_name = f"{package_url}:{tag}"
        logger.info(f"Getting image index for {self.qualified_name}")

        def _call_docker_inspect():
            proc = subprocess.run(
                [
                    shutil.which("docker"),
                    "buildx",
                    "imagetools",
                    "inspect",
                    "--raw",
                    self.qualified_name,
                ],
                capture_output=True,
                check=True,
            )

            self._data = json.loads(proc.stdout)

        retry_count = 0
        max_retries = 3

        while (retry_count < max_retries) and self._data is None:
            try:
                _call_docker_inspect()

            except subprocess.CalledProcessError as e:
                # Check for an i/o error and retry if so
                stderr_str = e.stderr.decode("ascii", "ignore")
                if "i/o timeout" in stderr_str:
                    logger.warning("i/o timeout, retrying")
                    retry_count += 1
                    time.sleep(0.5)
                    continue
                # Not a known error, raise
                logger.error(
                    f"Failed to get image index for {self.qualified_name}: {e.stderr}",
                )
                raise e
        if self._data is None:
            raise TimeoutError(f"Failed to get image index for {self.qualified_name}")

    @functools.cached_property
    def is_multi_arch(self) -> bool:
        return (
            self._data["mediaType"]
            in {
                "application/vnd.oci.image.index.v1+json",
                "application/vnd.docker.distribution.manifest.list.v2+json",
            }
            and "application/vnd.oci.image.layer"
            not in self._data["manifests"][0]["mediaType"]
        )

    @property
    def image_pointers(self) -> Iterator[MultiArchImageProperties]:
        for manifest_data in self._data["manifests"]:
            yield MultiArchImageProperties(manifest_data)


def check_tag_still_valid(owner: str, name: str, tag: str):
    """
    Checks the non-deleted tags are still valid.  The assumption is if the
    manifest is can be inspected and each image manifest if points to can be
    inspected, the image will still pull.

    https://github.com/opencontainers/image-spec/blob/main/image-index.md
    """

    def _check_image(full_name: str) -> bool:
        failed = False
        try:
            subprocess.run(
                [
                    shutil.which("docker"),
                    "buildx",
                    "imagetools",
                    "inspect",
                    "--raw",
                    full_name,
                ],
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to inspect digest: {e.stderr}")
            failed = True
        return failed

    a_tag_failed = False

    image_index = ImageIndexInfo(
        f"ghcr.io/{owner}/{name}",
        tag,
    )
    if not image_index.is_multi_arch:
        logger.info(f"Checking {image_index.qualified_name}")
        a_tag_failed = _check_image(image_index.qualified_name)
    else:
        for manifest in image_index.image_pointers:
            logger.info(f"Checking {manifest.digest} for {manifest.platform}")

            # This follows the pointer from the index to an actual image, layers and all
            # Note the format is @
            digest_name = f"ghcr.io/{owner}/{name}@{manifest.digest}"
            logger.debug(f"Inspecting {digest_name}")
            a_tag_failed = a_tag_failed or _check_image(digest_name)
            if a_tag_failed:
                logger.error("Failed to inspect digest")

    if a_tag_failed:
        raise Exception(f"tag {image_index.qualified_name} failed to inspect")
