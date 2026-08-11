"""Smoke tests for the initial project structure."""

import importlib


def test_main_module_can_be_imported() -> None:
    """The main application module is available and exposes its entry point."""
    module = importlib.import_module("app.main")

    assert callable(module.run)


def test_pytest_is_working() -> None:
    """A trivial assertion confirms the test runner executes the suite."""
    assert True
