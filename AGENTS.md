# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

This repo contains two GitHub Actions for cleaning up stale images on the GitHub Container Registry (ghcr.io):

1. **Ephemeral Image Cleaner** (`main_ephemeral.py`, `ephemeral/action.yml`) — removes images whose source branch has been deleted or pull request has been closed. Supports `branch` and `pull_request` naming schemes correlated via regex.
2. **Untagged Image Cleaner** (`main_untagged.py`, `untagged/action.yml`) — removes untagged image versions, skipping digests that are still referenced by a multi-arch image index.

Both actions are "safe by default": deletion only happens when `do_delete: "true"` is explicitly set. Without it, they log what would be deleted.

## Commands

```bash
# Install dependencies
uv sync --dev

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_packages.py

# Run a single test by name
uv run pytest tests/test_packages.py::test_function_name

# Lint (ruff linter + formatter)
uv run ruff check .
uv run ruff format .

# Pre-commit (runs ruff, prettier, yamlfmt, and general file checks)
uv run pre-commit run --all-files
```

## Architecture

### Entry Points

- `main_ephemeral.py` — async `_main()` orchestrates: check rate limits → get active packages → filter by regex → check branch/PR status → delete stale packages → verify remaining tags
- `main_untagged.py` — async `_main()` orchestrates: check rate limits → get all versions → split tagged/untagged → inspect multi-arch manifests to protect referenced digests → delete truly untagged → verify remaining tags

### Key Modules

**`github/`** — GitHub REST API clients, all extending `GithubApiBase` (async context manager wrapping `httpx.AsyncClient` with HTTP/2, retries, and automatic pagination via concurrent page fetching using `asyncio.TaskGroup`):

- `packages.py` — `GithubContainerRegistryOrgApi` / `GithubContainerRegistryUserApi`; `create_registry_api()` factory selects which based on `is_org`
- `branches.py` — `GithubBranchApi` for listing repo branches
- `pullrequest.py` — `GithubPullRequestApi` for checking PR closed state
- `ratelimit.py` — `GithubRateLimitApi` checked before any operation; also monitored per-response in `_check_rate_limit()`
- `models/` — typed dataclass/TypedDict models for API responses

**`regtools/`** — OCI registry client (direct HTTPS to ghcr.io, not via GitHub API):

- `images.py` — `RegistryClient` fetches manifests; `BearerAuth` handles token acquisition/caching for the OCI auth challenge flow; `check_tags_still_valid()` verifies kept tags after deletion
- `models.py` — TypedDicts for OCI/Docker manifest formats

**`utils/`**:

- `config.py` — `BaseConfig` dataclass (shared settings: token, owner, package name, delete flag, is_org, log level); `EphemeralConfig` extends it with scheme/repo/match_regex
- `errors.py` — `RateLimitError` raised when rate limit hit mid-operation
- `logging.py` — `setup_logging()` configures the root logger

### Configuration / Inputs

Both actions map GitHub Action inputs → CLI args → config dataclasses. The `delete` field defaults `False`; string `"true"`/`"false"` is coerced via `coerce_to_bool()` in `utils/__init__.py`.

### Testing

Tests live in `tests/` and use `pytest-asyncio`, `pytest-httpx` (for mocking HTTP), and `pytest-mock`. Fixtures for API clients are in `conftest.py`.

## Tooling

- **Package manager**: `uv` (required `>=0.9.0`, `uv.lock` is committed)
- **Linter/formatter**: `ruff` (line length 110, isort with force-single-line, auto-fix enabled)
- **Pre-commit**: enforces ruff, prettier (markdown/JS/TS), yamlfmt, and standard file hygiene hooks
- **Python**: 3.13+
