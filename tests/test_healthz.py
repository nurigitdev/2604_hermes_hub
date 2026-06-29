import anyio
import httpx

from app.main import create_app


async def get_healthz_response() -> httpx.Response:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/healthz")


def test_healthz_returns_ok() -> None:
    response = anyio.run(get_healthz_response)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
