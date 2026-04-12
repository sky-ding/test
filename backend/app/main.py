from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import SessionLocal, init_db
from app.routers import auth, manpower, phase, risk, users
from app.seed import seed_users


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_users(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="项目管理登记 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="pm_session",
    max_age=14 * 24 * 60 * 60,
    same_site=settings.session_same_site,
    https_only=settings.session_https_only,
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(manpower.router, prefix="/api/v1")
app.include_router(phase.router, prefix="/api/v1")
app.include_router(risk.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
