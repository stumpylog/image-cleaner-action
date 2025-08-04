# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.11.0] - 2025-08-04

### Added

- Initial unit testing of the GitHub API interactions

### Changed

- Updated astral-sh/setup-uv to v6.4.3
- Updates `uv` to 0.8.x
- Updates locked dependencies

## [0.10.0] - 2025-02-14

### Changed

- Dependency updates
- Updated astral-sh/setup-uv to v4
- Updated default Python to 3.12

## [0.9.0] - 2024-10-23

### Added

- Transition to `uv` for dependency and virtual environment management

### Changed

- Bump mypy from 1.11.0 to 1.11.1 (by @dependabot in [#102](https://github.com/stumpylog/image-cleaner-action/pull/102))
- Bump ruff from 0.5.5 to 0.6.1 (by @dependabot in [#105](https://github.com/stumpylog/image-cleaner-action/pull/105))
- Bump mypy from 1.11.1 to 1.13.0 (by @dependabot in [#120](https://github.com/stumpylog/image-cleaner-action/pull/120))
- Bump ruff from 0.6.1 to 0.7.0 (by @dependabot in [#118](https://github.com/stumpylog/image-cleaner-action/pull/118))
- Bump httpx from 0.27.0 to 0.27.2 (by @dependabot in [#109](https://github.com/stumpylog/image-cleaner-action/pull/109))

## [0.8.0] - 2024-07-30

### Fixed

- Resolved various reported issues from mypy

### Changed

- Bulk update of pre-commit hooks
- Bump certifi from 2024.2.2 to 2024.7.4 (by @dependabot in [#94](https://github.com/stumpylog/image-cleaner-action/pull/94))
- Bump ruff from 0.5.0 to 0.5.2 (by @dependabot in [#96](https://github.com/stumpylog/image-cleaner-action/pull/96))
- Bump setuptools from 69.5.1 to 70.0.0 (by @dependabot in [#97](https://github.com/stumpylog/image-cleaner-action/pull/97))
- Bump mypy from 1.10.1 to 1.11.0 (by @dependabot in [#99](https://github.com/stumpylog/image-cleaner-action/pull/99))
- Bump ruff from 0.5.2 to 0.5.5 (by @dependabot in [#100](https://github.com/stumpylog/image-cleaner-action/pull/100))
- Bump pre-commit from 3.7.1 to 3.8.0 (by @dependabot in [#101](https://github.com/stumpylog/image-cleaner-action/pull/101))

## [0.7.0] - 2024-06-03

### Changed

- Bump ruff from 0.3.7 to 0.4.3 (by @dependabot in [#84](https://github.com/stumpylog/image-cleaner-action/pull/84))
- Bump black from 24.4.0 to 24.4.2 (by @dependabot in [#81](https://github.com/stumpylog/image-cleaner-action/pull/81))
- Bump mypy from 1.9.0 to 1.10.0 (by @dependabot in [#82](https://github.com/stumpylog/image-cleaner-action/pull/82))
- Bump pre-commit from 3.7.0 to 3.7.1 (by @dependabot in [#86](https://github.com/stumpylog/image-cleaner-action/pull/86))
- Bump ruff from 0.4.3 to 0.4.5 (by @dependabot in [#87](https://github.com/stumpylog/image-cleaner-action/pull/87))
- Bump ruff from 0.4.5 to 0.4.7 (by @dependabot in [#88](https://github.com/stumpylog/image-cleaner-action/pull/88))
- Bumps actions/setup-python from v4 to v5

## [0.6.0] - 2024-04-15

### Changed

- Bump pre-commit from 3.6.2 to 3.7.0 (by @dependabot in #76)
- Bump ruff from 0.3.3 to 0.3.5 (by @dependabot in #77)
- Bump black from 24.3.0 to 24.4.0 (by @dependabot in #78)
- Bump ruff from 0.3.5 to 0.3.7 (by @dependabot in #79)

## [0.5.0] - 2024-02-06

### Changed

- Updated `pipenv` from 2023.10.24 to 2023.12.1
- Updated `httpx` from 0.25.1 to 0.26.0
- Updated development tool versions

## [0.4.0] - 2023-11-06

### Changed

- Bump actions/checkout from 3 to 4
- Bump httpx from 0.25.0 to 0.25.1
- Bump ruff from 0.0.292 to 0.1.0
- Updated `pipenv` from 2023.9.1 to 2023.10.24
- Fixed Ruff configuration
- Basically, dependencies were updated

## [0.3.0] - 2023-09-05

### Added

- CI enhancements to create a GitHub release with a changelog

### Changed

- Updated `pre-commit` hook versions, fixed old links, removed unneeded hooks
- Switch `black` hook to use its mirror for a speedup
- Updated `pipenv` from 2023.6.26 to 2023.9.1
- Updated Python version from 3.10 to 3.11
- Manually re-locked all Python dependencies

## [0.2.0] - 2023-07-20

### Added

- Added increased logging during initial information gathering
- Added better handling of encountering a rate limit while the action is executing

### Changed

- Bump `httpx` from 0.24.0 to 0.24.1
- Changelog format updated to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
- HTTP connection to the API now uses HTTP/2 if possible
- Updated `pipenv` from 2023.4.20 to 2023.6.26

## [0.1.0] - 2023-06-30

- Initial versioned release of the actions
