from datetime import date
from dataclasses import dataclass
from typing import Optional


@dataclass
class Cosecha:
    fecha: date
    cosechero_id: int
    finca_id: int
    kg: float
    parcela_id: Optional[int] = None
    tipo_cosecha: str = "HOJA FRESCA"
    monto_bs: float = 0
    observacion: Optional[str] = None
    id: Optional[int] = None
    lote_id: Optional[int] = None
    borrador: bool = False
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
    documento_recepcion: Optional[str] = None


@dataclass
class Movimiento:
    fecha: date
    detalle: str
    entrada_kg: float = 0
    salida_kg: float = 0
    saldo_kg: float = 0
    doc: Optional[str] = None
    lote_id: Optional[int] = None
    finca_id: Optional[int] = None
    observacion: Optional[str] = None
    id: Optional[int] = None
    cosecha_id: Optional[int] = None
    anula_movimiento_id: Optional[int] = None
    producto_id: Optional[int] = None
    producto: str = "Histórico sin clasificar"
    unidad: str = "kg"
    cantidad_entrada: float = 0
    cantidad_salida: float = 0
    cantidad_saldo: float = 0
    tipo: str = "movimiento"
