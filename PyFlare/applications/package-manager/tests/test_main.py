"""Basic smoke tests for Package Manager."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import pytest


def test_import():
    import main  # noqa: F401
    assert True


def test_version():
    import main
    assert hasattr(main, 'APP_VERSION')
    assert main.APP_VERSION == "1.0.0"
