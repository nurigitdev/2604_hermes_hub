from fastapi import FastAPI

from app.api.routes.admin import router as admin_router
from app.api.routes.admin_events import router as admin_events_router
from app.api.routes.admin_messages import router as admin_messages_router
from app.api.routes.agents import router as agents_router
from app.api.routes.auth import router as auth_router
from app.api.routes.events import router as events_router
from app.api.routes.messages import router as messages_router


def create_app() -> FastAPI:
    app = FastAPI(title="Hermes Agent Hub")
    app.include_router(admin_router)
    app.include_router(admin_events_router)
    app.include_router(admin_messages_router)
    app.include_router(agents_router)
    app.include_router(auth_router)
    app.include_router(events_router)
    app.include_router(messages_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
