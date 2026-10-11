"""Every admin write endpoint leaves an audit row (doc 06): each one must declare its action with
``Depends(audited(...))``. A new admin endpoint without it fails here."""

from fastapi.routing import APIRoute

from kuulis.asgi import app

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _calls(dependant) -> list:
    found = [dependant.call]
    for sub in dependant.dependencies:
        found += _calls(sub)
    return found


def _api_routes(routes) -> list[APIRoute]:
    """App routes, looking inside included routers (FastAPI keeps them as wrappers)."""
    found = []
    for route in routes:
        if isinstance(route, APIRoute):
            found.append(route)
        elif hasattr(route, "original_router"):
            found += _api_routes(route.original_router.routes)
    return found


def test_every_admin_write_endpoint_is_audited():
    routes = _api_routes(app.routes)
    assert len(routes) > 50  # the walk really reached the app's routers
    missing = []
    for route in routes:
        if not (route.methods & WRITE_METHODS):
            continue
        calls = _calls(route.dependant)
        is_admin = any(hasattr(call, "admin_roles") for call in calls)
        if is_admin and not any(hasattr(call, "audit_action") for call in calls):
            missing.append(f"{sorted(route.methods)} {route.path}")
    assert not missing, "Admin endpoints without audited(...):\n" + "\n".join(sorted(set(missing)))
