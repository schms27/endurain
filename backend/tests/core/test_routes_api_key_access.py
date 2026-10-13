"""Guard tests for which routes accept API-key authentication.

API keys are long-lived credentials, so the set of endpoints they can
reach is pinned here. Every protected operation of the mounted route
table is called with an API key (and no Bearer token) whose principal
holds every scope, so a route can only reject it by requiring a JWT.
Adding a route to the reachable set must be a deliberate change to
this file.
"""

import re
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import auth.constants as auth_constants
import auth.identity_service as auth_identity_service
import core.config as core_config
import core.database as core_database
import core.routes as core_routes
from auth.principal import ApiKeyCred, Principal

ROOT = core_config.ROOT_PATH

EXPECTED_API_KEY_ROUTES = {
    ("POST", f"{ROOT}/activities/create/upload"),
    ("GET", f"{ROOT}/activities/user/{{user_id}}/thisweek/stats"),
    ("GET", f"{ROOT}/activities/user/{{user_id}}/thismonth/stats"),
    ("GET", f"{ROOT}/activities/user/{{user_id}}/page_number/{{page_number}}/num_records/{{num_records}}"),
    ("GET", f"{ROOT}/activities_summaries/{{view_type}}"),
    ("GET", f"{ROOT}/gears"),
    ("GET", f"{ROOT}/health/sleep"),
    ("GET", f"{ROOT}/health/steps"),
    ("GET", f"{ROOT}/health/targets"),
    ("GET", f"{ROOT}/health/weight"),
    ("GET", f"{ROOT}/profile"),
}


@pytest.fixture(scope="module")
def api_key_reachable_routes() -> set[tuple[str, str]]:
    """
    Probe every protected operation with an all-scopes API key.

    Returns:
        Set of ``(method, path template)`` pairs that answer 401
        without credentials but not with the API key.
    """
    principal = Principal(
        user_id=1,
        username="alice",
        email="alice@example.com",
        is_active=True,
        is_superuser=False,
        scopes=frozenset(auth_constants.ADMIN_ACCESS_SCOPE),
        credential=ApiKeyCred(api_key_id=1, key_prefix="endurain"),
    )
    identity_service = MagicMock()
    identity_service.resolve_from_api_key.return_value = principal

    app = FastAPI()
    app.include_router(core_routes.router)
    app.dependency_overrides[auth_identity_service.get_identity_service] = lambda: identity_service
    app.dependency_overrides[core_database.get_db] = MagicMock

    reachable = set()
    with TestClient(app, raise_server_exceptions=False) as client:
        for path, operations in app.openapi()["paths"].items():
            for method, operation in operations.items():
                if not operation.get("security"):
                    continue  # public route
                url = re.sub(r"\{[^}]+\}", "1", path)
                headers = {"X-Client-Type": "mobile"}
                if client.request(method.upper(), url, headers=headers).status_code != 401:
                    continue  # needs no credentials at all (e.g. login)
                headers["X-API-Key"] = "endurain_test"
                if client.request(method.upper(), url, headers=headers).status_code != 401:
                    reachable.add((method.upper(), path))
    return reachable


class TestApiKeyRouteExposure:
    """Pin the API-key attack surface of the mounted routes."""

    def test_api_key_routes_match_expected(self, api_key_reachable_routes):
        """Only the allow-listed routes accept API keys."""
        assert api_key_reachable_routes == EXPECTED_API_KEY_ROUTES

    def test_write_routes_reject_api_keys(self, api_key_reachable_routes):
        """No state-changing route accepts API keys besides upload."""
        writes = {key for key in api_key_reachable_routes if key[0] != "GET"}
        assert writes == {("POST", f"{ROOT}/activities/create/upload")}
