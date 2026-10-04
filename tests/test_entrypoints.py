import logging
from argparse import Namespace

import pytest

import main_ephemeral
import main_untagged
from utils import get_log_level
from utils.log import setup_logging


def test_get_log_level_after_entrypoints_imported():
    # Regression: a utils/logging.py submodule shadowed the stdlib logging
    # module inside utils/__init__.py once an entry point imported it
    assert get_log_level("critical") == logging.CRITICAL
    assert get_log_level("debug") == logging.DEBUG
    assert get_log_level("nonsense") == logging.INFO


def test_ephemeral_config_from_args():
    args = Namespace(
        token="token",
        owner="owner",
        name="package",
        delete="false",
        is_org="true",
        loglevel="debug",
        scheme="branch",
        repo="repo",
        match_regex="(feature|fix)",
    )
    config = main_ephemeral.EphemeralConfig.from_args(args)
    assert config.log_level == logging.DEBUG
    assert config.is_org is True
    assert config.delete is False


def test_untagged_config_from_args():
    args = Namespace(
        token="token",
        owner="owner",
        name="package",
        delete="false",
        is_org="false",
        loglevel="warning",
    )
    config = main_untagged.UntaggedConfig.from_args(args)
    assert config.log_level == logging.WARNING


@pytest.mark.parametrize("level", [logging.INFO, logging.DEBUG])
def test_setup_logging(level):
    setup_logging(level)
