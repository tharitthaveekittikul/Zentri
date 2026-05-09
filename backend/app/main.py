import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    analysis, assets, auth, cash_balance, chat, dividends, documents,
    events, feature_llm_config, health, import_pipeline, ipos, llm_pricing, llm_usage,
    overview, pipeline, platforms, portfolio, provider_config, research, settings, system, watchlist,
)
from app.core.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="Zentri API", version="0.1.0")
logger.info("Zentri API starting up")


# Catch-all for any unhandled exception — FastAPI already handles HTTPException and
# RequestValidationError with correct {"detail": ...} JSON responses, so we only need
# this one handler for truly unexpected errors.
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    error_id = uuid.uuid4().hex[:8]
    logger.exception("Unhandled error [%s] on %s %s", error_id, request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}", "error_id": error_id},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(assets.router, prefix="/api/v1")
app.include_router(portfolio.router, prefix="/api/v1")
app.include_router(pipeline.router, prefix="/api/v1")
app.include_router(overview.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(provider_config.router, prefix="/api/v1")
app.include_router(feature_llm_config.router, prefix="/api/v1")
app.include_router(cash_balance.router, prefix="/api/v1")
app.include_router(import_pipeline.router, prefix="/api/v1")
app.include_router(llm_usage.router, prefix="/api/v1")
app.include_router(llm_pricing.router, prefix="/api/v1")
app.include_router(dividends.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(ipos.router, prefix="/api/v1")
app.include_router(watchlist.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(platforms.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(research.router, prefix="/api/v1")
