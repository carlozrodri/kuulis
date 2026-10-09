async def test_live(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_checks_db_and_redis(client):
    response = await client.get("/api/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["checks"] == {"database": True, "redis": True}
