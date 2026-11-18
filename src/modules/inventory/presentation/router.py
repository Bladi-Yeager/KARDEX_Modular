from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.modules.auth.presentation.dependencies import get_current_user, require_roles
from src.modules.inventory.application.dtos import (
    FincaAsignar,
    FincaCreate,
    FincaOut,
    ParcelaCreate,
    ParcelaOut,
    LoteCreate,
    LoteOut,
)
from src.modules.inventory.application.services import FincaService, ParcelaService, LoteService
from src.modules.inventory.infrastructure.repository_impl import FincaRepositoryImpl, ParcelaRepositoryImpl, LoteRepositoryImpl
from src.modules.inventory.domain.exceptions import FincaNoEncontrada, LoteDuplicado

router = APIRouter(prefix="/inventario", tags=["inventario"])

# Solo el administrador y el encargado pueden modificar el inventario.
puede_escribir = require_roles("admin", "encargado")


def get_finca_service(db: Session = Depends(get_db)) -> FincaService:
    return FincaService(FincaRepositoryImpl(db))


def get_parcela_service(db: Session = Depends(get_db)) -> ParcelaService:
    return ParcelaService(ParcelaRepositoryImpl(db), FincaRepositoryImpl(db))


def get_lote_service(db: Session = Depends(get_db)) -> LoteService:
    return LoteService(LoteRepositoryImpl(db))


@router.get("/fincas", response_model=list[FincaOut])
def listar_fincas(
    service: FincaService = Depends(get_finca_service),
    _user=Depends(get_current_user),
):
    return service.list_all()


@router.post("/fincas", response_model=FincaOut)
def crear_finca(
    data: FincaCreate,
    service: FincaService = Depends(get_finca_service),
    _user=Depends(puede_escribir),
):
    return service.create(data)


@router.put("/fincas/{finca_id}/asignar", response_model=FincaOut)
def asignar_finca(
    finca_id: int,
    data: FincaAsignar,
    service: FincaService = Depends(get_finca_service),
    _admin=Depends(require_roles("admin")),
):
    """Asigna una finca a un productor (usuario con rol cliente).

    Enviar usuario_id = null para quitar la asignacion.
    """
    try:
        return service.asignar_usuario(finca_id, data.usuario_id)
    except FincaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/parcelas", response_model=list[ParcelaOut])
def listar_parcelas(
    service: ParcelaService = Depends(get_parcela_service),
    _user=Depends(get_current_user),
):
    return service.list_all()


@router.post("/parcelas", response_model=ParcelaOut)
def crear_parcela(
    data: ParcelaCreate,
    service: ParcelaService = Depends(get_parcela_service),
    _user=Depends(puede_escribir),
):
    try:
        return service.create(data)
    except FincaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/lotes", response_model=list[LoteOut])
def listar_lotes(
    service: LoteService = Depends(get_lote_service),
    _user=Depends(get_current_user),
):
    return service.list_all()


@router.post("/lotes", response_model=LoteOut)
def crear_lote(
    data: LoteCreate,
    service: LoteService = Depends(get_lote_service),
    _user=Depends(puede_escribir),
):
    try:
        return service.create(data)
    except LoteDuplicado as e:
        raise HTTPException(status_code=400, detail=str(e))
