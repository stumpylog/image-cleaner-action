# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Bump ruff from 0.3.7 to 0.4.3 (by @dependabot in [#84](https://github.com/stumpylog/image-cleaner-action/pull/84))
- Bump black from 24.4.0 to 24.4.2 (by @dependabot in [#81](https://github.com/stumpylog/image-cleaner-action/pull/81))

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
