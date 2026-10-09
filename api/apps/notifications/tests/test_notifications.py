async def test_register_device_is_idempotent(client, user_headers):
    payload = {"push_token": "ExponentPushToken[abc123xyz]", "platform": "ios"}
    first = await client.post("/api/v1/notifications/devices", json=payload, headers=user_headers)
    second = await client.post("/api/v1/notifications/devices", json=payload, headers=user_headers)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


async def test_staff_sends_notification_to_user(client, staff_headers, user_headers):
    me = (await client.get("/api/v1/users/me", headers=user_headers)).json()
    response = await client.post(
        "/api/v1/notifications/send",
        json={"title": "Hola", "body": "Bienvenido", "user_id": me["id"]},
        headers=staff_headers,
    )
    assert response.status_code == 202

    count = (await client.get("/api/v1/notifications/unread-count", headers=user_headers)).json()
    assert count["unread"] == 1

    inbox = (await client.get("/api/v1/notifications", headers=user_headers)).json()
    notification_id = inbox["items"][0]["id"]
    read = await client.post(f"/api/v1/notifications/{notification_id}/read", headers=user_headers)
    assert read.json()["read_at"] is not None


async def test_broadcast_reaches_all_active_users(client, staff_headers, user_headers):
    response = await client.post(
        "/api/v1/notifications/send", json={"title": "Aviso"}, headers=staff_headers
    )
    assert response.status_code == 202
    inbox = (await client.get("/api/v1/notifications", headers=user_headers)).json()
    assert inbox["total"] == 1


async def test_users_cannot_send_notifications(client, user_headers):
    response = await client.post(
        "/api/v1/notifications/send", json={"title": "x"}, headers=user_headers
    )
    assert response.status_code == 403
