async def test_me_requires_auth(client):
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_me_and_update(client, user_headers):
    response = await client.patch(
        "/api/v1/users/me", json={"full_name": "Carlos", "locale": "en"}, headers=user_headers
    )
    assert response.status_code == 200
    me = (await client.get("/api/v1/users/me", headers=user_headers)).json()
    assert me["full_name"] == "Carlos"
    assert me["locale"] == "en"


async def test_change_password(client, user_headers):
    response = await client.post(
        "/api/v1/users/me/password",
        json={"current_password": "Sup3r-secret!", "new_password": "N3w-password!"},
        headers=user_headers,
    )
    assert response.status_code == 204


async def test_regular_user_cannot_list_users(client, user_headers):
    response = await client.get("/api/v1/users", headers=user_headers)
    assert response.status_code == 403


async def test_staff_can_list_and_search_users(client, staff_headers, user_headers):
    response = await client.get("/api/v1/users?search=user@", headers=staff_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["email"] == "user@example.com"


async def test_staff_cannot_change_roles(client, staff_headers, user_headers):
    users = (await client.get("/api/v1/users", headers=staff_headers)).json()["items"]
    target = next(u for u in users if u["email"] == "user@example.com")
    response = await client.patch(
        f"/api/v1/users/{target['id']}", json={"role": "admin"}, headers=staff_headers
    )
    assert response.status_code == 403


async def test_admin_manages_users(client, admin_headers):
    created = await client.post(
        "/api/v1/users",
        json={"email": "staff2@example.com", "password": "Sup3r-secret!", "role": "staff"},
        headers=admin_headers,
    )
    assert created.status_code == 201
    user_id = created.json()["id"]
    updated = await client.patch(
        f"/api/v1/users/{user_id}", json={"is_active": False}, headers=admin_headers
    )
    assert updated.json()["is_active"] is False
    stats = (await client.get("/api/v1/users/stats", headers=admin_headers)).json()
    assert stats["total"] == 2
    assert stats["by_role"]["staff"] == 1


async def test_admin_cannot_demote_self(client, admin_headers):
    me = (await client.get("/api/v1/users/me", headers=admin_headers)).json()
    response = await client.patch(
        f"/api/v1/users/{me['id']}", json={"role": "user"}, headers=admin_headers
    )
    assert response.status_code == 403
