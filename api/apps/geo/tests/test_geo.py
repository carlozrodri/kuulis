import httpx
import pytest

from apps.config.schemas import AppConfig
from apps.geo import clients
from kuulis.settings import settings

AREA = AppConfig().service_area


@pytest.fixture
def mock_http(monkeypatch):
    """Routes every provider call to ``handler`` (no network in tests)."""
    calls: list[httpx.Request] = []
    responses: dict[str, httpx.Response] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        for prefix, response in responses.items():
            if request.url.path.startswith(prefix):
                return response
        return httpx.Response(500)

    monkeypatch.setattr(clients, "_http", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(settings, "OSRM_URL", "http://osrm.test")
    monkeypatch.setattr(settings, "PHOTON_URL", "http://photon.test")
    return calls, responses


def _feature(lat, lng, **props):
    return {"geometry": {"coordinates": [lng, lat]}, "properties": props}


async def test_route_estimate_without_osrm(monkeypatch):
    monkeypatch.setattr(settings, "OSRM_URL", "")
    route = await clients.route(10.49, -66.88, 10.50, -66.85)
    straight = clients.haversine_m(10.49, -66.88, 10.50, -66.85)
    assert route.distance_m == round(straight * 1.3)
    assert route.duration_s == round(straight * 1.3 / (22 / 3.6))
    assert route.polyline is None


async def test_route_osrm_and_fallback(mock_http):
    calls, responses = mock_http
    responses["/route/v1/driving/"] = httpx.Response(
        200,
        json={"code": "Ok", "routes": [{"distance": 4321.4, "duration": 600.6, "geometry": "abc"}]},
    )
    route = await clients.route(10.49, -66.88, 10.50, -66.85)
    assert (route.distance_m, route.duration_s, route.polyline) == (4321, 601, "abc")
    assert "-66.880000,10.490000;-66.850000,10.500000" in str(calls[0].url)

    responses["/route/v1/driving/"] = httpx.Response(503)
    fallback = await clients.route(10.49, -66.88, 10.50, -66.85)
    assert fallback.polyline is None and fallback.distance_m > 0


async def test_search_limited_to_area_and_cached(mock_http):
    calls, responses = mock_http
    responses["/api"] = httpx.Response(
        200,
        json={
            "features": [
                _feature(
                    10.496,
                    -66.853,
                    name="Centro Sambil",
                    street="Av. Libertador",
                    district="Chacao",
                    city="Caracas",
                ),
                _feature(10.49, -66.85, street="Calle 1", housenumber="5", city="Caracas"),
                _feature(10.65, -71.61, name="Sambil Maracaibo", city="Maracaibo"),
            ]
        },
    )
    results = await clients.search("  sambil ", AREA, 10.5, -66.9)
    assert [r.name for r in results] == ["Centro Sambil", "Calle 1 5"]
    assert results[0].address == "Av. Libertador, Chacao, Caracas"
    params = calls[0].url.params
    assert params["q"] == "sambil" and params["bbox"] == "-67.1,10.35,-66.7,10.56"
    assert await clients.search("Sambil", AREA, 10.5, -66.9) == results
    assert len(calls) == 1  # second search served from Redis


async def test_search_without_provider_or_on_error(mock_http, monkeypatch):
    _, responses = mock_http
    responses["/api"] = httpx.Response(502)
    assert await clients.search("altamira", AREA) == []
    monkeypatch.setattr(settings, "PHOTON_URL", "")
    assert await clients.search("altamira", AREA) == []


async def test_reverse(mock_http, monkeypatch):
    _, responses = mock_http
    responses["/reverse"] = httpx.Response(
        200, json={"features": [_feature(10.4961, -66.8531, name="Plaza Altamira", city="Caracas")]}
    )
    result = await clients.reverse(10.49612, -66.85311)
    assert result.name == "Plaza Altamira" and result.address == "Caracas"
    assert (result.lat, result.lng) == (10.49612, -66.85311)
    monkeypatch.setattr(settings, "PHOTON_URL", "")
    plain = await clients.reverse(10.5, -66.9)
    assert plain.name == "10.50000, -66.90000"


async def test_geo_endpoints_require_auth_and_work(client, user_headers, monkeypatch):
    monkeypatch.setattr(settings, "PHOTON_URL", "")
    assert (await client.get("/api/v1/geo/search?q=x")).status_code == 401
    response = await client.get("/api/v1/geo/search?q=altamira", headers=user_headers)
    assert response.status_code == 200 and response.json() == []
    response = await client.get("/api/v1/geo/reverse?lat=10.5&lng=-66.9", headers=user_headers)
    assert response.json()["lat"] == 10.5
