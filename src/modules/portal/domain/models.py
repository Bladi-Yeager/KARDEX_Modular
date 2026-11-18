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


@dataclass
class LoteDelProductor:
    id: int
    codigo: str
    finca: Optional[str]
    fecha_ingreso: date
    detalle: Optional[str]
