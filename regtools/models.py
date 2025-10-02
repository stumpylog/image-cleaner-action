from collections.abc import Mapping
from collections.abc import Sequence
from typing import Literal
from typing import NotRequired
from typing import TypedDict

Annotations = Mapping[str, str]  # typically keys/values are strings
StringSeq = Sequence[str]

# --------------------------
# Platform (strict spec keys)
# --------------------------
Platform = TypedDict(
    "Platform",
    {
        "architecture": str,
        "os": str,
        "os.version": NotRequired[str],
        "os.features": NotRequired[Sequence[str]],
        "variant": NotRequired[str],
        "features": NotRequired[Sequence[str]],
    },
)


# --------------------------
# Descriptor (OCI descriptor)
# --------------------------
class Descriptor(TypedDict, total=False):
    """
    application/vnd.oci.descriptor.v1+json
    See: https://github.com/opencontainers/image-spec/blob/main/descriptor.md
    """

    mediaType: Literal["application/vnd.oci.descriptor.v1+json"]
    size: int
    digest: str
    urls: NotRequired[Sequence[str]]
    annotations: NotRequired[Mapping[str, str]]
    platform: NotRequired[Platform]
    artifactType: NotRequired[str]


# --------------------------
# OCI image index
# --------------------------
class OCIImageIndex(TypedDict):
    """
    application/vnd.oci.image.index.v1+json
    """

    schemaVersion: int
    mediaType: NotRequired[Literal["application/vnd.oci.image.index.v1+json"]]
    manifests: Sequence[Descriptor]
    annotations: NotRequired[Mapping[str, str]]


# --------------------------
# Docker manifest list
# --------------------------
class DockerManifestList(TypedDict):
    """
    application/vnd.docker.distribution.manifest.list.v2+json
    """

    schemaVersion: int
    mediaType: NotRequired[Literal["application/vnd.docker.distribution.manifest.list.v2+json"]]
    manifests: Sequence[Descriptor]
    annotations: NotRequired[Annotations]


# --------------------------
# OCI manifest
# --------------------------
class OCIManifest(TypedDict):
    """
    application/vnd.oci.image.manifest.v1+json
    See: https://github.com/opencontainers/image-spec/blob/main/manifest.md
    """

    schemaVersion: int
    mediaType: NotRequired[Literal["application/vnd.oci.image.manifest.v1+json"]]
    config: Descriptor
    layers: Sequence[Descriptor]
    annotations: NotRequired[Annotations]


class DockerManifestV2(TypedDict):
    """
    application/vnd.docker.distribution.manifest.v2+json
    This is similar to an OCIManifest in practice but historically different constants.
    """

    schemaVersion: int
    mediaType: NotRequired[Literal["application/vnd.docker.distribution.manifest.v2+json"]]
    config: Descriptor
    layers: Sequence[Descriptor]
    annotations: NotRequired[Annotations]
