from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.schemas import RootResponse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aiwardrobe_api.routers import (
    ai,
    auth,
    billing,
    designer,
    health,
    items,
    looks,
    marketplace,
    outfits,
    privacy,
    style,
    uploads,
    wishlist,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
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
    for router in (
        health.router,
        auth.router,
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
                "uploads",
                "items",
                "looks",
                "outfits",
                "ai",
                "designer",
                "marketplace",
                "wishlist",
                "style-dna",
                "privacy",
                "billing",
            ],
        )

    return app


app = create_app()
