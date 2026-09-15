import logging
import os

from dotenv import load_dotenv

# must run before any local module reads os.environ at import time
# (database.py reads DATABASE_URL, llm_client.py reads LLM_* as soon as
# they're imported below)
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from .database import Base, engine
from . import models  # noqa: F401 - ensures models are registered before create_all
from .routers import candidates, campaigns, screenings, leaderboard
from .services.campaign_runner import reconcile_stale_state

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("globalvox.main")

Base.metadata.create_all(bind=engine)
reconcile_stale_state()

app = FastAPI(title="GlobalVox AI Screening", version="1.0.0")

DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
allowed_origins = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(candidates.router)
app.include_router(campaigns.router)
app.include_router(screenings.router)
app.include_router(leaderboard.router)


@app.exception_handler(SQLAlchemyError)
async def db_error_handler(request: Request, exc: SQLAlchemyError):
    # a raw DB error (e.g. a constraint violation that slipped past
    # application-level validation) should never leak a stack trace or an
    # opaque 500 with no explanation -- log the real error, tell the client
    # something sane happened without exposing internals.
    logger.exception("Unhandled database error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "A database error occurred. Please try again."})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our end. Please try again."})


@app.get("/api/health")
def health():
    return {"status": "ok"}
