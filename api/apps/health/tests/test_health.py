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
