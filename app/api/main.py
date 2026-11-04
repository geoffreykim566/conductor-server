"""The FastAPI app: lifespan, middleware, and every router. Run: uvicorn app.api.main:app.
Conversation state is round-tripped by the client, never stored here: README.md."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import middleware
from app.api.admin import router as admin_router
from app.api.routes import chat, feedback, me, ratings, register, waitlist
from app.core import db
from app.core.config import CORS_ORIGINS
from app.core.ratelimit import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    try:
        yield
    finally:
        await db.disconnect()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(RequestValidationError, middleware.log_validation_errors)
app.middleware("http")(middleware.reject_oversized_bodies)
# Only the landing page's signup form is called from a browser.
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS,
                   allow_methods=["POST"], allow_headers=["Content-Type"])

for module in (register, me, ratings, feedback, waitlist, chat):
    app.include_router(module.router)
app.include_router(admin_router)
