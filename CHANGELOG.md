# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2023-09-05

### Added

- CI enhancements to create a GitHub release with a changelog

### Changed

- Updated `pre-commit` hook versions, fixed old links, removed unneeded hooks
- Switch `black` hook to use its mirror for a speedup
- Updated `pipenv` from `2023.6.26 to 2023.9.1
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
