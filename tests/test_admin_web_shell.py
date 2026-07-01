import anyio
import httpx
from fastapi import FastAPI


async def get_path(app: FastAPI, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        follow_redirects=False,
    ) as client:
        return await client.get(path)


def test_admin_root_redirects_to_dashboard(test_app: FastAPI) -> None:
    response = anyio.run(get_path, test_app, "/admin")

    assert response.status_code == 307
    assert response.headers["location"] == "/admin/dashboard"


def test_site_root_redirects_to_admin_dashboard(test_app: FastAPI) -> None:
    response = anyio.run(get_path, test_app, "/")

    assert response.status_code == 307
    assert response.headers["location"] == "/admin/dashboard"


def test_admin_login_serves_web_shell(test_app: FastAPI) -> None:
    response = anyio.run(get_path, test_app, "/admin/login")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Hermes Agent Hub" in response.text
    assert 'data-view="login"' in response.text


def test_admin_dashboard_serves_web_shell(test_app: FastAPI) -> None:
    response = anyio.run(get_path, test_app, "/admin/dashboard")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'data-view="app"' in response.text
    assert "Dashboard" in response.text


def test_admin_agents_serves_web_shell(test_app: FastAPI) -> None:
    response = anyio.run(get_path, test_app, "/admin/agents")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'data-page="agents"' in response.text
    assert "Agent Registry" in response.text


def test_admin_messages_serves_web_shell(test_app: FastAPI) -> None:
    response = anyio.run(get_path, test_app, "/admin/messages")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'data-page="messages"' in response.text
    assert 'data-message-drawer' in response.text
    assert "Raw Payload" in response.text
    assert "Message Explorer" in response.text


def test_admin_static_assets_are_served(test_app: FastAPI) -> None:
    response = anyio.run(get_path, test_app, "/admin/static/admin.js")

    assert response.status_code == 200
    assert "loadMessages" in response.text
    assert "openMessageDetail" in response.text
    assert "data-related-message-id" in response.text
