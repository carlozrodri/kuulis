"""The app's copy of the API error codes (doc 20) stays in sync with the source."""

from kuulis.core.error_codes import EXPORT_PATH, collect, render


def test_known_codes_are_found():
    codes = collect()
    assert "ride_invalid_transition" in codes  # AppError subclass attribute
    assert "password_too_common" in codes  # AppError(..., code=...)
    assert "idempotency_key_reused" in codes  # answered by the middleware


def test_export_is_up_to_date():
    assert EXPORT_PATH.read_text() == render(), (
        "A new error code: run `python manage.py error-codes` and translate it in the app"
    )
