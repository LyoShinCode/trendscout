"""Точка входа. Swagger UI: /docs · ReDoc: /redoc · OpenAPI: /openapi.json."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import DOCS_DIR, FRONTEND_DIR, PRESENTATION_DIR
from app.database import SessionLocal, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from app.models import SimState
    from app.seed import generate
    db = SessionLocal()
    try:
        if db.get(SimState, 1) is None:
            generate(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="TrendScout API",
    version="1.0.0",
    description="ПО для автоматизированного анализа структурированных данных "
                "(алгоритм RB-DETECT). ИАР · Бородуля А.В.",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/v1/health", tags=["meta"])
def health():
    return {"status": "ok", "stage": 3, "service": "TrendScout"}


from app.api import alerts, catalog, engine as engine_api  # noqa: E402

for r in (catalog.router, alerts.router, engine_api.router):
    app.include_router(r)

app.mount("/presentation", StaticFiles(directory=PRESENTATION_DIR, html=True), name="presentation")
app.mount("/sa-docs", StaticFiles(directory=DOCS_DIR), name="sa-docs")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
