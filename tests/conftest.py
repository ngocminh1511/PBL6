import pytest


@pytest.fixture(autouse=True)
def no_startup_probe(monkeypatch):
    """Automated tests never reach cloud services; the startup probe is opted in per test."""
    monkeypatch.setenv("HEALTH_PROBE_ON_STARTUP", "false")
