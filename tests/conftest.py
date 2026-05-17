"""Root conftest: preserve sys.stdout so pytest capture survives cycle test imports."""
import sys
import pytest


@pytest.fixture(autouse=True, scope="session")
def _preserve_stdout():
    """Some legacy cycle test files replace sys.stdout at import time.
    Save and restore the real stdout so pytest's capture mechanism doesn't break."""
    original = sys.stdout
    yield
    sys.stdout = original
