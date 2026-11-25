from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.modules.auth.presentation.dependencies import require_roles, validar_productor
from src.modules.inventory.application.dtos import (
    FincaAsignar,
    FincaCreate,
    FincaOut,
    ParcelaCreate,
    ParcelaOut,
    LoteCreate,
    LoteOut,
    ProductoCreate,
    ProductoOut,
)
from src.modules.inventory.application.services import FincaService, ParcelaService, LoteService
from src.modules.inventory.infrastructure.repository_impl import FincaRepositoryImpl, ParcelaRepositoryImpl, LoteRepositoryImpl
from src.modules.inventory.domain.exceptions import FincaNoEncontrada, LoteDuplicado
from src.modules.inventory.infrastructure.models_db import ProductoDB

router = APIRouter(prefix="/inventario", tags=["inventario"])

puede_leer = require_roles("admin")
puede_escribir = require_roles("admin")


@router.get("/productos", response_model=list[ProductoOut])
def listar_productos(db: Session = Depends(get_db), _actor=Depends(puede_leer)):
    return db.query(ProductoDB).order_by(ProductoDB.nombre, ProductoDB.unidad).all()


@router.post("/productos", response_model=ProductoOut, status_code=201)
def crear_producto(data: ProductoCreate, db: Session = Depends(get_db), _actor=Depends(puede_escribir)):
    row = ProductoDB(**data.model_dump())
    db.add(row)
    try:
        db.commit()
    except IntegrityError as error:
        raise HTTPException(409, "Ese producto ya existe con la misma unidad.") from error
    return row


def get_finca_service(db: Session = Depends(get_db)) -> FincaService:
    return FincaService(FincaRepositoryImpl(db))


def get_parcela_service(db: Session = Depends(get_db)) -> ParcelaService:
    return ParcelaService(ParcelaRepositoryImpl(db), FincaRepositoryImpl(db))


def get_lote_service(db: Session = Depends(get_db)) -> LoteService:
    return LoteService(LoteRepositoryImpl(db))


@router.get("/fincas", response_model=list[FincaOut])
def listar_fincas(
    service: FincaService = Depends(get_finca_service),
    _user=Depends(puede_leer),
):
    return service.list_all()


@router.post("/fincas", response_model=FincaOut)
def crear_finca(
    data: FincaCreate,
    service: FincaService = Depends(get_finca_service),
    db: Session = Depends(get_db),
    _user=Depends(puede_escribir),
):
    validar_productor(db, data.usuario_id)
    try:
        return service.create(data)
    except IntegrityError as error:
        raise HTTPException(409, "El número de finca ya está registrado.") from error


@router.put("/fincas/{finca_id}/asignar", response_model=FincaOut)
def asignar_finca(
    finca_id: int,
    data: FincaAsignar,
    service: FincaService = Depends(get_finca_service),
    db: Session = Depends(get_db),
    _admin=Depends(require_roles("admin")),
):
    """Asigna una finca a un productor (usuario con rol cliente).

    Enviar usuario_id = null para quitar la asignacion.
    """
    validar_productor(db, data.usuario_id)
    try:
        return service.asignar_usuario(finca_id, data.usuario_id)
    except FincaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/parcelas", response_model=list[ParcelaOut])
def listar_parcelas(
    service: ParcelaService = Depends(get_parcela_service),
    _user=Depends(puede_leer),
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
    except IntegrityError as error:
        raise HTTPException(409, "El número de parcela ya está registrado en esa finca.") from error


@router.get("/lotes", response_model=list[LoteOut])
def listar_lotes(
    service: LoteService = Depends(get_lote_service),
    _user=Depends(puede_leer),
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
