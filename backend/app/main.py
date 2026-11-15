from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import settings
from app.database import SessionLocal
from app.demo_data import ensure_demo
from app.domain.errors import DomainError


@asynccontextmanager
async def lifespan(_: FastAPI):
    with SessionLocal() as session:
        ensure_demo(session)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="团队 AI 工作交接助手 Demo",
        version="0.1.0",
        description="人工确认、版本绑定、主动接收的本地演示 API。",
        lifespan=lifespan,
    )

    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, error: DomainError):
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "details": error.details,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, error: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "输入内容不符合要求，请检查标记字段",
                    "details": {"errors": error.errors()},
                }
            },
        )

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    app.include_router(router)

    dist = Path(settings.frontend_dist)
    assets = dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "NOT_FOUND", "message": "API 路径不存在"}},
            )
        index = dist / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse(
            status_code=404,
            content={"message": "前端尚未构建，请在开发模式使用 Vite。"},
        )

    return app


app = create_app()
