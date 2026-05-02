from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analysis, assets, auth, cash_balance, documents, feature_llm_config, health, import_pipeline, overview, pipeline, platforms, portfolio, provider_config, settings
from app.core.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="Zentri API", version="0.1.0")
logger.info("Zentri API starting up")

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
app.include_router(platforms.router, prefix="/api/v1")
app.include_router(portfolio.router, prefix="/api/v1")
app.include_router(pipeline.router, prefix="/api/v1")
app.include_router(overview.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(provider_config.router, prefix="/api/v1")
app.include_router(feature_llm_config.router, prefix="/api/v1")
app.include_router(cash_balance.router, prefix="/api/v1")
app.include_router(import_pipeline.router, prefix="/api/v1")
