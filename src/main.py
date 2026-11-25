from pathlib import Path
from src.modules.inventory.bitacora import router as bitacora_router
from src.modules.reportes.direccion import router as direccion_router

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.core.database import Base, engine
from src.core.demo_data import seed_demo_data
from src.core.config import settings
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
from src.modules.kardex.domain.exceptions import OperacionKardexError
from src.modules.reportes.router import router as reportes_router
from src.modules.reportes.finanzas import router as finanzas_router

app = FastAPI(
    title="Kardex Agricola API",
    version="3.5.0",
    description=(
        "Sistema Kardex Agricola (monolito modular - DDD). "
        "Incluye el portal de solo lectura para el productor."
    ),
)

# Crea las tablas que falten y actualiza una base de datos antigua sin perder datos.
Base.metadata.create_all(bind=engine)
run_migrations()

# Datos de ejemplo (solo la primera vez, si la base esta vacia).
if settings.DEMO_DATA:
    seed_demo_data()


@app.exception_handler(OperacionKardexError)
async def error_kardex(_request, error):
    return JSONResponse(status_code=error.status, content={"detail": str(error)})

app.include_router(bitacora_router)
app.include_router(direccion_router)
app.include_router(auth_router)
app.include_router(supliers_router)
app.include_router(inventory_router)
app.include_router(kardex_router)
app.include_router(portal_router)
app.include_router(reportes_router)
app.include_router(finanzas_router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/portal/static", StaticFiles(directory=STATIC_DIR / "portal"), name="portal-static")
app.mount("/inicio/static", StaticFiles(directory=STATIC_DIR / "inicio"), name="inicio-static")
app.mount("/admin/static", StaticFiles(directory=STATIC_DIR / "admin"), name="admin-static")


@app.get("/", include_in_schema=False)
def raiz():
    """Al entrar a localhost:8001 se abre el centro de accesos."""
    return FileResponse(STATIC_DIR / "inicio" / "index.html")


@app.get("/inicio", include_in_schema=False)
def inicio():
    """Centro de accesos: administrador, productor y base de datos."""
    return FileResponse(STATIC_DIR / "inicio" / "index.html")


@app.get("/portal", include_in_schema=False)
def portal_inicio():
    return FileResponse(STATIC_DIR / "portal" / "index.html")


@app.get("/portal/panel", include_in_schema=False)
def portal_panel():
    return FileResponse(STATIC_DIR / "portal" / "panel.html")


@app.get("/admin", include_in_schema=False)
def admin_panel():
    """Panel completo de administracion, encargados y trabajadores."""
    return FileResponse(STATIC_DIR / "admin" / "index.html")


@app.get("/health", tags=["sistema"])
def health():
    return {"msg": "Kardex Agricola API funcionando", "version": app.version}


@app.get("/jefe", include_in_schema=False)
def panel_jefe():
    return FileResponse(STATIC_DIR / "direccion" / "index.html")


@app.get("/soporte", include_in_schema=False)
def panel_soporte():
    return RedirectResponse("https://wa.me/59167559408", status_code=307)
