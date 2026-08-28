"""
Settings validators — the ones that stop a foot-gun at boot.
"""

from __future__ import annotations

import pytest

from app.config import Settings


def test_test_database_url_must_be_a_dedicated_test_database():
    """
    escalasPT's conftest points the suite at DATABASE_URL and then calls
    drop_all. Running pytest with a dev .env deletes the dev database. Here the
    setting refuses to load at all.
    """
    with pytest.raises(ValueError, match="_test"):
        Settings(TEST_DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/caderno")


def test_test_database_url_accepts_a_test_database():
    settings = Settings(TEST_DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/caderno_test")

    assert settings.TEST_DATABASE_URL.endswith("caderno_test")


def test_encryption_keys_must_be_real_keys_when_set():
    with pytest.raises(ValueError, match="IDENT_FIELD_KEY"):
        Settings(IDENT_FIELD_KEY="GENERATE_ME")


def test_encryption_keys_may_be_empty_while_the_feature_is_off():
    assert Settings(IDENT_FIELD_KEY="").IDENT_FIELD_KEY == ""


def test_localhost_cors_is_stripped_outside_development():
    settings = Settings(
        APP_ENV="production",
        CORS_ORIGINS='["http://localhost:5173","https://caderno.tailnet.ts.net"]',
    )

    assert settings.cors_origins_list == ["https://caderno.tailnet.ts.net"]
