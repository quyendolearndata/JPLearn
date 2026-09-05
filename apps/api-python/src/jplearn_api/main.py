import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.exceptions import HTTPException as StarletteHTTPException

from jplearn_api.alert import alert_worker, drain_alert_queue
from jplearn_api.db import create_engine_and_sessions
from jplearn_api.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from jplearn_api.middleware import RequestIdMiddleware
from jplearn_api.openapi_diff import normalize_security_scheme_names
from jplearn_api.routers import auth, catalog, flags, health, media, sessions
from jplearn_api.settings import Settings, get_settings
from jplearn_api.storage import LocalFilesystemStorage, StoragePort


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    engine, factory = create_engine_and_sessions(settings)
    app.state.engine = engine
    app.state.sessionmaker = factory

    alert_queue = getattr(app.state, "alert_queue", None)
    if alert_queue is None:
        alert_queue = asyncio.Queue(maxsize=1000)
        app.state.alert_queue = alert_queue

    worker_task = asyncio.create_task(alert_worker(alert_queue, settings))
    yield
    await drain_alert_queue(alert_queue, worker_task, timeout=3.0)
    await engine.dispose()


def create_app(
    settings: Settings | None = None,
    storage: StoragePort | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    storage = storage or LocalFilesystemStorage(settings.storage_root or (Path.cwd() / "storage"))
    app = FastAPI(
        title="JPLearn Platform API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.openapi_ui else None,
        redoc_url="/redoc" if settings.openapi_ui else None,
        openapi_url="/openapi.json" if settings.openapi_ui else None,
    )
    app.state.settings = settings
    app.state.storage = storage
    app.state.alert_queue = asyncio.Queue(maxsize=1000)
    app.add_middleware(RequestIdMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(flags.router)
    app.include_router(catalog.router)
    app.include_router(sessions.router)
    app.include_router(media.router)

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        schema = normalize_security_scheme_names(schema)
        components = schema.setdefault("components", {})
        schemas = components.setdefault("schemas", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes.setdefault(
            "signedQuery",
            {
                "type": "apiKey",
                "in": "query",
                "name": "sig",
                "description": "HMAC-SHA256 signature for media streaming (with exp timestamp)",
            },
        )

        schemas["HttpError"] = {
            "type": "object",
            "description": "Standard JSON error body (400, 403, 404, 500) per ADR-005",
            "required": ["statusCode", "message", "error"],
            "properties": {
                "statusCode": {"type": "integer"},
                "message": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ]
                },
                "error": {"type": "string"},
            },
        }
        schemas["Http401Error"] = {
            "type": "object",
            "description": "Distinct 401 Unauthorized JSON error body per ADR-005",
            "required": ["statusCode", "message"],
            "properties": {
                "statusCode": {"type": "integer", "enum": [401]},
                "message": {"type": "string"},
            },
        }

        # Strip auto-generated 422 per ADR-005 BA contract (runtime validates to 400 Bad Request)
        for path_name, path_item in schema.get("paths", {}).items():
            if isinstance(path_item, dict):
                for op in path_item.values():
                    if isinstance(op, dict) and "responses" in op:
                        op["responses"].pop("422", None)
                        for code, resp in op["responses"].items():
                            if code == "401":
                                if "content" not in resp:
                                    resp["content"] = {
                                        "application/json": {
                                            "schema": {"$ref": "#/components/schemas/Http401Error"}
                                        }
                                    }
                            elif code in ("400", "403", "404", "500"):
                                if "content" not in resp:
                                    resp["content"] = {
                                        "application/json": {
                                            "schema": {"$ref": "#/components/schemas/HttpError"}
                                        }
                                    }
                            elif code == "503" and path_name == "/ready":
                                if "content" not in resp:
                                    resp["content"] = {
                                        "application/json": {
                                            "schema": {"$ref": "#/components/schemas/Ready"}
                                        }
                                    }

        schemas.pop("HTTPValidationError", None)
        schemas.pop("ValidationError", None)
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
    return app


class _LazyApp:
    def __init__(self) -> None:
        self._inner: FastAPI | None = None

    def _app(self) -> FastAPI:
        if self._inner is None:
            self._inner = create_app()
        return self._inner

    def __getattr__(self, name: str):
        return getattr(self._app(), name)

    async def __call__(self, scope, receive, send):
        await self._app()(scope, receive, send)


app = _LazyApp()
