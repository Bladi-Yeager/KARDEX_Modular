from datetime import date
from typing import Optional

from pydantic import BaseModel
from src.modules.inventory.application.dtos import Unidad


class FincaPortalOut(BaseModel):
    id: int
    numero: int
    nombre: Optional[str] = None
    ubicacion: Optional[str] = None
    parcelas: int = 0
    hectareas: float = 0

    class Config:
        from_attributes = True


class ProductoPortal(BaseModel):
    producto_id: int | None = None
    producto: str
    unidad: Unidad


class CosechaPortalOut(ProductoPortal):
    id: int
    fecha: date
    finca: Optional[str] = None
    parcela: Optional[str] = None
    cosechero: Optional[str] = None
    tipo_cosecha: str
    kg: float
    monto_bs: float
    observacion: Optional[str] = None
    cantidad: float
    recibida: float | None = None
    rechazada: float | None = None
    motivo_rechazo: str | None = None
    cantidad_secundaria: float | None = None
    unidad_secundaria: Unidad | None = None
    fecha_recepcion: date | None = None
    codigo_lote: str | None = None
    documento_recepcion: str | None = None

    class Config:
        from_attributes = True


class MovimientoPortalOut(ProductoPortal):
    id: int
    fecha: date
    detalle: str
    doc: Optional[str] = None
    lote: Optional[str] = None
    finca: Optional[str] = None
    entrada_kg: float
    salida_kg: float
    saldo_kg: float
    observacion: Optional[str] = None
    cantidad_entrada: float
    cantidad_salida: float
    cantidad_saldo: float
    tipo: str
    anula_movimiento_id: int | None = None

    class Config:
        from_attributes = True


class LotePortalOut(ProductoPortal):
    id: int
    codigo: str
    finca: Optional[str] = None
    fecha_ingreso: date
    detalle: Optional[str] = None
    cosecha_id: Optional[int] = None

    class Config:
        from_attributes = True


class ResumenPortalOut(BaseModel):
    productor: str
    username: str
    fincas: int
    hectareas: float
    total_cosechas: int
    total_kg: float
    total_monto_bs: float
    entradas_kg: float
    salidas_kg: float
    saldo_kg: float
    ultima_actividad: Optional[date] = None
    tiene_datos: bool
    existencias: list["ExistenciaPortal"]


class ExistenciaPortal(ProductoPortal):
    entrada: float
    salida: float
    saldo: float


class ClienteAdminOut(BaseModel):
    id: int
    username: str
    nombre_completo: str
    activo: bool
    fincas: list[FincaPortalOut] = []
