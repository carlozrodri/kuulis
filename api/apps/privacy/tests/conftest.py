import pytest

# Shared ride fixtures (fake realtime/push recorder, passenger).
from apps.rides.tests.conftest import passenger, recorder  # noqa: F401
from kuulis.core import storage
from kuulis.core.exceptions import ServiceUnavailableError


@pytest.fixture(autouse=True)
def _no_storage(monkeypatch) -> None:
    """Never write to a real bucket from tests, even when the machine has S3 credentials."""

    def disabled(*_args, **_kwargs):
        raise ServiceUnavailableError("Storage is not configured", code="storage_disabled")

    monkeypatch.setattr(storage, "put_object", disabled)
    monkeypatch.setattr(storage, "delete_objects", lambda keys: False)
