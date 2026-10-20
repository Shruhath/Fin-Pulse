"""The FinPulse API. Run with `finpulse serve`; the OpenAPI document at /openapi.json is the contract."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from finpulse.core.logging import configure_logging
from finpulse.core.settings import get_settings

from .routers import analyze, ask, corpus, eval, system


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="FinPulse API",
        version="0.1.0",
        description="Entity-level sentiment, events and source-grounded summaries for Indian disclosures.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    for router in (corpus.router, eval.router, analyze.router, ask.router, system.router):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
