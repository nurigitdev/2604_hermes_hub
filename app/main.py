from fastapi import FastAPI

from app.api.routes.auth import router as auth_router


def create_app() -> FastAPI:
    app = FastAPI(title="Hermes Agent Hub")
    app.include_router(auth_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
