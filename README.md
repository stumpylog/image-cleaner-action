
## The Problem

Many actions in a repository will end up creating a Docker image stored on the GitHub Container Registry
(ghcr.io).  This is quite useful, as another developer can pull the image to test your build code or a
user can confirm the fix worked as expected.  The image may be built on each push to a certain named branch or
when a pull request is created or updated.

But what about after the fix has been made, the feature tested or the pull request merged?  Do you really
need to keep the Docker image around, accessible and cluttering up your packages?  That makes it harder for a
user to locate the last released tags.  If you're paying for the storage space, each image takes up some
amount of storage as well.

In an ideal world, there would be a retention policy or reaper configuration to easily remove images
based on some configuration.

## The Solution

This actions aims to simplify the cleaning of containers which are meant to be ephemeral.  Once
their job is completed, they don't need to exist in the registry.
