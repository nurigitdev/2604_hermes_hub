from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

WEB_DIR = Path(__file__).resolve().parent
WEB_STATIC_DIR = WEB_DIR / "static"
ADMIN_SHELL_PATH = WEB_DIR / "templates" / "admin.html"

router = APIRouter(include_in_schema=False)


@router.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/admin/dashboard", status_code=307)


@router.get("/admin")
def admin_root() -> RedirectResponse:
    return RedirectResponse(url="/admin/dashboard", status_code=307)


@router.get("/admin/login")
def admin_login() -> FileResponse:
    return FileResponse(ADMIN_SHELL_PATH)


@router.get("/admin/dashboard")
def admin_dashboard() -> FileResponse:
    return FileResponse(ADMIN_SHELL_PATH)


@router.get("/admin/agents")
def admin_agents() -> FileResponse:
    return FileResponse(ADMIN_SHELL_PATH)


@router.get("/admin/agent-tokens")
def admin_agent_tokens() -> FileResponse:
    return FileResponse(ADMIN_SHELL_PATH)


@router.get("/admin/enrollment")
def admin_enrollment() -> RedirectResponse:
    return RedirectResponse(url="/admin/agent-tokens", status_code=307)


@router.get("/admin/messages")
def admin_messages() -> FileResponse:
    return FileResponse(ADMIN_SHELL_PATH)
