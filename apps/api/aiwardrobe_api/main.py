from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.logging import configure_logging
from aiwardrobe_core.schemas import RootResponse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aiwardrobe_api.logging_middleware import RequestLoggingMiddleware
from aiwardrobe_api.rate_limit import RateLimitMiddleware
from aiwardrobe_api.routers import (
    ai,
    auth,
    avatar,
    billing,
    codex_runner,
    designer,
    health,
    items,
    looks,
    marketplace,
    outfits,
    privacy,
    style,
    uploads,
    weather,
    wishlist,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_file_for("api"))
    production_errors = settings.production_startup_errors()
    if production_errors:
        raise RuntimeError("Production startup blocked by unsafe configuration: " + ", ".join(production_errors))
    app.state.settings = settings
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI Digital Wardrobe API",
        version="0.1.0",
        description="FastAPI backend for Telegram Bot + Mini App AI wardrobe.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.miniapp_public_url, "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.add_middleware(RequestLoggingMiddleware)
    for router in (
        health.router,
        codex_runner.router,
        auth.router,
        avatar.router,
        uploads.router,
        items.router,
        looks.router,
        outfits.router,
        ai.router,
        designer.router,
        marketplace.router,
        wishlist.router,
        style.router,
        privacy.router,
        weather.router,
        billing.router,
    ):
        app.include_router(router)

    @app.get("/", response_model=RootResponse, tags=["root"])
    async def root() -> RootResponse:
        return RootResponse(
            name="AI Digital Wardrobe API",
            version=app.version,
            status="ok",
            docs_url="/docs",
            health_url="/health",
            miniapp_url=settings.miniapp_public_url,
            api_groups=[
                "auth",
                "avatar",
                "uploads",
                "items",
                "looks",
                "outfits",
                "ai",
                "designer",
                "marketplace",
                "wishlist",
                "style-dna",
                "weather",
                "privacy",
                "billing",
            ],
        )

    return app


app = create_app()
