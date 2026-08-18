"""Session ownership regression tests for authenticated actors."""

from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_optional_user
from app.main import app


@contextmanager
def _use_real_auth():
    """Temporarily bypass shared-test authentication overrides."""
    previous_current = app.dependency_overrides.pop(get_current_user, None)
    previous_optional = app.dependency_overrides.pop(get_optional_user, None)
    try:
        yield
    finally:
        if previous_current is not None:
            app.dependency_overrides[get_current_user] = previous_current
        if previous_optional is not None:
            app.dependency_overrides[get_optional_user] = previous_optional


def _create_session(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/api/simulations",
        headers=headers,
        json={
            "scenario_id": "milktea_startup",
            "decision_vars": {"budget": 200000, "span_years": 1},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _assert_foreign_session_is_hidden(
    client: TestClient,
    session_id: str,
    headers: dict[str, str],
) -> None:
    for path in (
        "/api/sessions",
        "/api/sessions?scenario_id=milktea_startup",
    ):
        visible_ids = {
            item["id"] for item in client.get(path, headers=headers).json()
        }
        assert session_id not in visible_ids
    assert client.get(f"/api/sessions/{session_id}", headers=headers).status_code == 404
    assert (
        client.get(
            f"/api/sessions/{session_id}/report-detail",
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/simulations/{session_id}/report",
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/simulations/{session_id}/ask",
            headers=headers,
            json={"question": "请总结这次推演"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/simulations/{session_id}/resume",
            headers=headers,
            json={"choice": "继续"},
        ).status_code
        == 404
    )


def test_guest_session_requests_are_rejected():
    with _use_real_auth(), TestClient(app) as client:
        response = client.post(
            "/api/simulations",
            headers={"X-Yanjie-Guest-Id": "guest-owner-a"},
            json={
                "scenario_id": "milktea_startup",
                "decision_vars": {"budget": 200000, "span_years": 1},
            },
        )

    assert response.status_code == 401


def test_authenticated_sessions_are_isolated():
    with _use_real_auth(), TestClient(app) as client:
        register_a = client.post(
            "/api/auth/register",
            json={
                "username": "isolation_a",
                "email": "isolation_a@example.com",
                "password": "secret123",
            },
        )
        register_b = client.post(
            "/api/auth/register",
            json={
                "username": "isolation_b",
                "email": "isolation_b@example.com",
                "password": "secret123",
            },
        )
        assert register_a.status_code == 201, register_a.text
        assert register_b.status_code == 201, register_b.text

        user_a = {
            "Authorization": f"Bearer {register_a.json()['access_token']}"
        }
        user_b = {
            "Authorization": f"Bearer {register_b.json()['access_token']}"
        }

        session_a = _create_session(client, user_a)
        session_b = _create_session(client, user_b)

        _assert_foreign_session_is_hidden(client, session_a, user_b)
        _assert_foreign_session_is_hidden(client, session_b, user_a)
