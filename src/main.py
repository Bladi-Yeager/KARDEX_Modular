from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.core.database import Base, engine
from src.core.migrate import run_migrations
from src.modules.auth.infrastructure import models_db as auth_models
from src.modules.supliers.infrastructure import models_db as supliers_models
from src.modules.inventory.infrastructure import models_db as inventory_models
from src.modules.kardex.infrastructure import models_db as kardex_models
from src.modules.auth.presentation.router import router as auth_router
from src.modules.supliers.presentation.router import router as supliers_router
from src.modules.inventory.presentation.router import router as inventory_router
from src.modules.kardex.presentation.router import router as kardex_router
from src.modules.portal.presentation.router import router as portal_router

app = FastAPI(
    title="Kardex Agricola API",
    version="2.0.0",
    description=(
        "Sistema Kardex Agricola (monolito modular - DDD). "
        "Incluye el portal de solo lectura para el productor."
    ),
)

# Crea las tablas que falten y actualiza una base de datos antigua sin perder datos.
Base.metadata.create_all(bind=engine)
run_migrations()

app.include_router(auth_router)
app.include_router(supliers_router)
app.include_router(inventory_router)
app.include_router(kardex_router)
app.include_router(portal_router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/portal/static", StaticFiles(directory=STATIC_DIR / "portal"), name="portal-static")


@app.get("/", include_in_schema=False)
def raiz():
    """Al entrar a localhost:8001 se abre directamente el portal del productor."""
    return RedirectResponse(url="/portal")


@app.get("/portal", include_in_schema=False)
def portal_inicio():
    return FileResponse(STATIC_DIR / "portal" / "index.html")


@app.get("/portal/panel", include_in_schema=False)
def portal_panel():
    return FileResponse(STATIC_DIR / "portal" / "panel.html")


@app.get("/health", tags=["sistema"])
def health():
    return {"msg": "Kardex Agricola API funcionando", "version": "2.0.0"}
