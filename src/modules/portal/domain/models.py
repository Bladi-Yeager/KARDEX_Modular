"""Modelos de solo lectura que ve el productor en su portal."""

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class FincaDelProductor:
    id: int
    numero: int
    nombre: Optional[str]
    ubicacion: Optional[str]
    parcelas: int = 0
    hectareas: float = 0.0


@dataclass
class CosechaDelProductor:
    id: int
    fecha: date
    finca: Optional[str]
    parcela: Optional[str]
    cosechero: Optional[str]
    tipo_cosecha: str
    kg: float
    monto_bs: float
    observacion: Optional[str]
    producto_id: Optional[int] = None
    producto: str = "Histórico sin clasificar"
    unidad: str = "kg"
    cantidad: float = 0
    recibida: Optional[float] = None
    rechazada: Optional[float] = None
    motivo_rechazo: Optional[str] = None
    cantidad_secundaria: Optional[float] = None
    unidad_secundaria: Optional[str] = None
    fecha_recepcion: Optional[date] = None
    codigo_lote: Optional[str] = None
    documento_recepcion: Optional[str] = None


@dataclass
class MovimientoDelProductor:
    id: int
    fecha: date
    detalle: str
    doc: Optional[str]
    lote: Optional[str]
    finca: Optional[str]
    entrada_kg: float
    salida_kg: float
    saldo_kg: float
    observacion: Optional[str]
    producto_id: Optional[int] = None
    producto: str = "Histórico sin clasificar"
    unidad: str = "kg"
    cantidad_entrada: float = 0
    cantidad_salida: float = 0
    cantidad_saldo: float = 0
    tipo: str = "movimiento"
    anula_movimiento_id: Optional[int] = None


@dataclass
class LoteDelProductor:
    id: int
    codigo: str
    finca: Optional[str]
    fecha_ingreso: date
    detalle: Optional[str]
    cosecha_id: Optional[int] = None
    producto_id: Optional[int] = None
    producto: str = "Histórico sin clasificar"
    unidad: str = "kg"
