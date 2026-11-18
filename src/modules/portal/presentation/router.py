from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.modules.auth.infrastructure.repository_impl import UsuarioRepositoryImpl
from src.modules.auth.presentation.dependencies import get_current_user, require_roles
from src.modules.inventory.application.dtos import FincaAsignar, FincaOut
from src.modules.inventory.application.services import FincaService
from src.modules.inventory.domain.exceptions import FincaNoEncontrada
from src.modules.inventory.infrastructure.repository_impl import FincaRepositoryImpl
from src.modules.portal.application.dtos import (
    ClienteAdminOut,
    CosechaPortalOut,
    FincaPortalOut,
    LotePortalOut,
    MovimientoPortalOut,
    ResumenPortalOut,
)
from src.modules.portal.application.services import PortalService
from src.modules.portal.infrastructure.repository_impl import PortalRepositoryImpl

router = APIRouter(prefix="/portal/api", tags=["portal del productor"])

# El productor (cliente) entra aqui. El admin tambien puede revisar.
puede_ver_portal = require_roles("cliente", "admin")


def get_portal_service(db: Session = Depends(get_db)) -> PortalService:
    return PortalService(PortalRepositoryImpl(db))


@router.get("/resumen", response_model=ResumenPortalOut)
def resumen(
    usuario=Depends(puede_ver_portal),
    service: PortalService = Depends(get_portal_service),
):
    """Totales del productor: kg cosechados, monto, entradas, salidas y saldo."""
    return service.resumen(usuario)


@router.get("/mis-fincas", response_model=list[FincaPortalOut])
def mis_fincas(
    usuario=Depends(puede_ver_portal),
    service: PortalService = Depends(get_portal_service),
):
    return service.fincas(usuario)


@router.get("/mis-cosechas", response_model=list[CosechaPortalOut])
def mis_cosechas(
    usuario=Depends(puede_ver_portal),
    service: PortalService = Depends(get_portal_service),
):
    return service.cosechas(usuario)


@router.get("/mi-kardex", response_model=list[MovimientoPortalOut])
def mi_kardex(
    usuario=Depends(puede_ver_portal),
    service: PortalService = Depends(get_portal_service),
):
    """Libro Kardex del productor: entradas, salidas y saldo."""
    return service.movimientos(usuario)


@router.get("/mis-lotes", response_model=list[LotePortalOut])
def mis_lotes(
    usuario=Depends(puede_ver_portal),
    service: PortalService = Depends(get_portal_service),
):
    return service.lotes(usuario)


# --------------------------------------------------------------------- admin
@router.get("/admin/clientes", response_model=list[ClienteAdminOut])
def listar_clientes(
    db: Session = Depends(get_db),
    _admin=Depends(require_roles("admin")),
):
    """Para el gerente: que clientes existen y que fincas tiene cada uno."""
    service = PortalService(PortalRepositoryImpl(db))
    return service.clientes(UsuarioRepositoryImpl(db))


@router.post("/admin/asignar-finca", response_model=FincaOut)
def asignar_finca(
    data: dict,
    db: Session = Depends(get_db),
    _admin=Depends(require_roles("admin")),
):
    """Asigna una finca a un cliente. Cuerpo: {"finca_id": 1, "usuario_id": 2}."""
    finca_id = data.get("finca_id")
    usuario_id = data.get("usuario_id")
    if not finca_id:
        raise HTTPException(status_code=400, detail="Falta finca_id")

    servicio = FincaService(FincaRepositoryImpl(db))
    try:
        return servicio.asignar_usuario(int(finca_id), usuario_id)
    except FincaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))
