async def test_live(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_checks_db_and_redis(client):
    response = await client.get("/api/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["checks"] == {"database": True, "redis": True}


async def test_stripped_prefix_is_restored(client, user_headers):
    # Coolify/Traefik may strip "/api" from https://host/api/v1/... before it reaches us.
    response = await client.get("/v1/users/me", headers=user_headers)
    assert response.status_code == 200


def test_settings_parse_csv_env_for_every_environment(monkeypatch):
    from kuulis.settings.local import LocalSettings
    from kuulis.settings.production import ProductionSettings
    from kuulis.settings.qa import QASettings

    monkeypatch.setenv("CORS_ORIGINS", "https://a.example.com, https://b.example.com")
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@db:5432/kuulis")
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    for cls in (LocalSettings, QASettings, ProductionSettings):
        s = cls()
        assert s.CORS_ORIGINS == ["https://a.example.com", "https://b.example.com"]
        assert str(s.DATABASE_URL).startswith("postgresql+asyncpg://")
