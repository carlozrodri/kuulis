"""Settings split by environment, Django style.

The active module is chosen with ``APP_ENV`` (local | test | qa | production).
Every value can be overridden with an environment variable of the same name.
"""

import os
from functools import lru_cache

from kuulis.settings.base import BaseAppSettings


@lru_cache
def get_settings() -> BaseAppSettings:
    env = os.getenv("APP_ENV", "local").lower()
    if env == "production":
        from kuulis.settings.production import ProductionSettings

        return ProductionSettings()
    if env == "qa":
        from kuulis.settings.qa import QASettings

        return QASettings()
    if env == "test":
        from kuulis.settings.test import TestSettings

        return TestSettings()
    from kuulis.settings.local import LocalSettings

    return LocalSettings()


settings = get_settings()

__all__ = ["BaseAppSettings", "get_settings", "settings"]
