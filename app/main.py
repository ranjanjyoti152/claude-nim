from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.routers import auth_api, gateway, keys, models_api, usage_api

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_indexes()
    yield
    await db.close()


app = FastAPI(title="Anthropic Gateway for NVIDIA NIM", lifespan=lifespan)

# API routers
app.include_router(auth_api.router)
app.include_router(keys.router)
app.include_router(models_api.router)
app.include_router(usage_api.router)
# Gateway (Anthropic-compatible) endpoints — mounted at root (/v1/...)
app.include_router(gateway.router)


@app.head("/")
def head_root() -> Response:
    # Claude Code sends a HEAD / connectivity probe.
    return Response(status_code=200)


# --- Frontend (served last so it doesn't shadow API routes) ---
@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/dashboard")
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
