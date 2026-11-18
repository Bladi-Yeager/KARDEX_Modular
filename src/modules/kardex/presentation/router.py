from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.modules.auth.presentation.dependencies import get_current_user, require_roles
from src.modules.kardex.application.dtos import CosechaCreate, CosechaOut, MovimientoCreate, MovimientoOut
from src.modules.kardex.application.services import CosechaService, MovimientoService
from src.modules.kardex.infrastructure.repository_impl import CosechaRepositoryImpl, MovimientoRepositoryImpl
from src.modules.kardex.domain.exceptions import CosechaNoEncontrada

router = APIRouter(prefix="/kardex", tags=["kardex"])

puede_escribir = require_roles("admin", "encargado")


def get_cosecha_service(db: Session = Depends(get_db)) -> CosechaService:
    return CosechaService(CosechaRepositoryImpl(db))


def get_movimiento_service(db: Session = Depends(get_db)) -> MovimientoService:
    return MovimientoService(MovimientoRepositoryImpl(db))


@router.get("/cosechas", response_model=list[CosechaOut])
def listar_cosechas(
    service: CosechaService = Depends(get_cosecha_service),
    _user=Depends(get_current_user),
):
    return service.list_all()


@router.post("/cosechas", response_model=CosechaOut)
def crear_cosecha(
    data: CosechaCreate,
    service: CosechaService = Depends(get_cosecha_service),
    _user=Depends(puede_escribir),
):
    return service.create(data)


@router.get("/cosechas/total-kg")
def total_kg_mes(
    anio: int,
    mes: int,
    service: CosechaService = Depends(get_cosecha_service),
    _user=Depends(get_current_user),
):
    total = service.total_kg_by_month(anio, mes)
    return {"anio": anio, "mes": mes, "total_kg": total}


@router.get("/movimientos", response_model=list[MovimientoOut])
def listar_movimientos(
    service: MovimientoService = Depends(get_movimiento_service),
    _user=Depends(get_current_user),
):
    return service.list_all()


@router.post("/movimientos", response_model=MovimientoOut)
def crear_movimiento(
    data: MovimientoCreate,
    service: MovimientoService = Depends(get_movimiento_service),
    _user=Depends(puede_escribir),
):
    return service.create(data)
