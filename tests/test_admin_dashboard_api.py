import anyio
import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.admin_seed import seed_admin_user


async def login_and_get_dashboard_summary(app: FastAPI) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "change-me-admin-password"},
        )
        return await client.get("/admin/api/dashboard/summary")


async def get_dashboard_summary_without_login(app: FastAPI) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/admin/api/dashboard/summary")


def seed_admin(db_session: Session) -> None:
    seed_admin_user(
        db_session,
        Settings(
            admin_email="admin@example.com",
            admin_name="Admin User",
            admin_password="change-me-admin-password",
        ),
    )


def test_admin_can_get_dashboard_summary(test_app: FastAPI, db_session: Session) -> None:
    seed_admin(db_session)

    response = anyio.run(login_and_get_dashboard_summary, test_app)

    assert response.status_code == 200
    assert response.json() == {
        "total_agent_count": 0,
        "active_agent_count": 0,
        "unmapped_agent_count": 0,
        "messages_today_count": 0,
        "events_last_24h_count": 0,
        "error_events_last_24h_count": 0,
    }


def test_dashboard_summary_requires_admin_session(test_app: FastAPI) -> None:
    response = anyio.run(get_dashboard_summary_without_login, test_app)

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
