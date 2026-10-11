"""Password policy: at least 8 characters (schemas) and not one of the most common passwords.

The list (``data/common_passwords.txt.gz``) is the NCSC top 100 000 from SecLists, lowercased and
reduced to the ones with 8 or more characters, plus a few local ones (Spanish, Venezuela, Kuulis).
It is checked locally: passwords never leave the server.
"""

import gzip
from functools import cache
from pathlib import Path

from kuulis.core.exceptions import AppError

_LIST = Path(__file__).parent / "data" / "common_passwords.txt.gz"


@cache
def _common() -> frozenset[str]:
    with gzip.open(_LIST, "rt", encoding="utf-8") as file:
        return frozenset(line.strip() for line in file if line.strip())


def is_common(password: str) -> bool:
    return password.strip().lower() in _common()


def ensure_allowed(password: str) -> None:
    if is_common(password):
        raise AppError("This password is too common", code="password_too_common")
