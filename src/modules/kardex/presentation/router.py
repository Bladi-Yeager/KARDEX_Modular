from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.modules.auth.presentation.dependencies import require_roles
from src.modules.kardex.application.dtos import (
    AnulacionCreate, CosechaCreate, CosechaOut, MovimientoCreate, MovimientoOut, RecepcionCreate, RecepcionOut,
)
from src.modules.kardex.application.services import CosechaService, MovimientoService
from src.modules.kardex.infrastructure.repository_impl import CosechaRepositoryImpl, MovimientoRepositoryImpl

router = APIRouter(prefix="/kardex", tags=["kardex"])
puede_leer = require_roles("admin", "jefe")
puede_escribir = require_roles("admin")


def get_cosecha_service(db: Session = Depends(get_db)) -> CosechaService:
    return CosechaService(CosechaRepositoryImpl(db))


def get_movimiento_service(db: Session = Depends(get_db)) -> MovimientoService:
    return MovimientoService(MovimientoRepositoryImpl(db))


@router.get("/cosechas", response_model=list[CosechaOut])
def listar_cosechas(service: CosechaService = Depends(get_cosecha_service), _actor=Depends(puede_leer)):
    return [c for c in service.list_all() if _actor.rol == "admin" or not c.borrador]


@router.post("/cosechas", response_model=CosechaOut, status_code=201)
def crear_cosecha(data: CosechaCreate, service: CosechaService = Depends(get_cosecha_service), _actor=Depends(puede_escribir)):
    return service.create(data)


@router.get("/cosechas/total-kg")
def total_kg_mes(anio: int, mes: int, service: CosechaService = Depends(get_cosecha_service), _actor=Depends(puede_leer)):
    return {"anio": anio, "mes": mes, "total_kg": service.total_kg_by_month(anio, mes)}


@router.put("/cosechas/{cosecha_id}", response_model=CosechaOut)
def editar_cosecha(cosecha_id: int, data: CosechaCreate,
                   service: CosechaService = Depends(get_cosecha_service), _actor=Depends(puede_escribir)):
    return service.editar(cosecha_id, data)


@router.delete("/cosechas/{cosecha_id}", status_code=204)
def eliminar_cosecha(cosecha_id: int, service: CosechaService = Depends(get_cosecha_service),
                     _actor=Depends(puede_escribir)):
    service.eliminar(cosecha_id)


@router.post("/cosechas/{cosecha_id}/recepcion", response_model=RecepcionOut, status_code=201)
def recibir_cosecha(cosecha_id: int, data: RecepcionCreate,
                   service: MovimientoService = Depends(get_movimiento_service), actor=Depends(puede_escribir)):
    return service.recibir(cosecha_id, data, actor.id)


@router.get("/movimientos", response_model=list[MovimientoOut])
def listar_movimientos(finca_id: int | None = None, lote_id: int | None = None,
                       producto_id: int | None = Query(None, ge=0),
                       service: MovimientoService = Depends(get_movimiento_service),
                       _actor=Depends(puede_leer)):
    return service.list_all(finca_id, lote_id, producto_id)


@router.post("/movimientos", response_model=MovimientoOut, status_code=201)
def crear_movimiento(data: MovimientoCreate, service: MovimientoService = Depends(get_movimiento_service),
                     actor=Depends(puede_escribir)):
    return service.create(data, actor.id)


@router.post("/movimientos/{movimiento_id}/anular", response_model=MovimientoOut, status_code=201)
def anular_movimiento(movimiento_id: int, data: AnulacionCreate,
                      service: MovimientoService = Depends(get_movimiento_service), actor=Depends(puede_escribir)):
    return service.anular(movimiento_id, data.motivo, actor.id)
