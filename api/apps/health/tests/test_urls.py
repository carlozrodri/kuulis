"""kuulis/urls.py orders the routers by traffic, not by meaning: no route may hide another."""

import re

from fastapi import APIRouter
from fastapi.routing import APIRoute
from starlette.routing import compile_path

from kuulis.urls import api_v1

SAMPLE_ID = "00000000-0000-0000-0000-000000000001"


def _routes(router: APIRouter, prefix: str = "") -> list[tuple[str, set[str], object]]:
    found = []
    for route in router.routes:
        included = getattr(route, "original_router", None)  # FastAPI >= 0.137 keeps sub-routers
        if included is not None:
            found += _routes(included, prefix + (route.include_context.prefix or ""))
        elif isinstance(route, APIRoute):
            found.append((prefix + route.path, route.methods, route.endpoint))
    return found


def test_every_route_is_reachable():
    routes = _routes(api_v1)
    compiled = [(compile_path(path)[0], methods, endpoint) for path, methods, endpoint in routes]
    hidden = []
    for path, methods, endpoint in routes:
        sample = re.sub(r"\{[^}]+\}", SAMPLE_ID, path)
        for method in methods:
            first = next(e for rx, m, e in compiled if method in m and rx.match(sample))
            if first is not endpoint:
                hidden.append(f"{method} {path}")
    assert hidden == []
