from datetime import date
from typing import Optional

from pydantic import BaseModel


class FincaPortalOut(BaseModel):
    id: int
    numero: int
    nombre: Optional[str] = None
    ubicacion: Optional[str] = None
    parcelas: int = 0
    hectareas: float = 0

    class Config:
        from_attributes = True


class CosechaPortalOut(BaseModel):
    id: int
    fecha: date
    finca: Optional[str] = None
    parcela: Optional[str] = None
    cosechero: Optional[str] = None
    tipo_cosecha: str
    kg: float
    monto_bs: float
    observacion: Optional[str] = None

    class Config:
        from_attributes = True


class MovimientoPortalOut(BaseModel):
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

    class Config:
        from_attributes = True


class LotePortalOut(BaseModel):
    id: int
    codigo: str
    finca: Optional[str] = None
    fecha_ingreso: date
    detalle: Optional[str] = None

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


class ClienteAdminOut(BaseModel):
    id: int
    username: str
    nombre_completo: str
    activo: bool
    fincas: list[FincaPortalOut] = []
