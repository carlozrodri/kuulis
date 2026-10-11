API = "/api/v1/users/me/places"
HOME = {"kind": "home", "address": "Res. El Ávila, Los Palos Grandes", "lat": 10.5, "lng": -66.84}


async def test_home_is_replaced_and_others_listed(client, user_headers):
    first = await client.post(API, json=HOME, headers=user_headers)
    assert first.status_code == 201, first.text
    again = await client.post(API, json=HOME | {"address": "Nueva casa"}, headers=user_headers)
    assert again.json()["id"] == first.json()["id"]
    assert again.json()["address"] == "Nueva casa"

    gym = await client.post(
        API,
        json={"label": "  Gym ", "address": "Sambil", "lat": 10.49, "lng": -66.85},
        headers=user_headers,
    )
    assert gym.status_code == 201 and gym.json()["label"] == "Gym"
    await client.post(API, json=HOME | {"kind": "work", "address": "Torre"}, headers=user_headers)

    places = (await client.get(API, headers=user_headers)).json()
    assert [p["kind"] for p in places] == ["home", "work", "other"]


async def test_update_delete_and_ownership(client, user_headers, staff_headers):
    place = (await client.post(API, json=HOME, headers=user_headers)).json()
    renamed = await client.patch(
        f"{API}/{place['id']}", json={"label": "Casa de mamá"}, headers=user_headers
    )
    assert renamed.json()["label"] == "Casa de mamá"

    other = await client.delete(f"{API}/{place['id']}", headers=staff_headers)
    assert other.status_code == 404
    assert other.json()["error"]["code"] == "place_not_found"

    assert (await client.delete(f"{API}/{place['id']}", headers=user_headers)).status_code == 204
    assert (await client.get(API, headers=user_headers)).json() == []


async def test_other_places_limit(client, user_headers):
    body = {"address": "X", "lat": 10.4, "lng": -66.8}
    for _ in range(10):
        assert (await client.post(API, json=body, headers=user_headers)).status_code == 201
    response = await client.post(API, json=body, headers=user_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "too_many_places"
