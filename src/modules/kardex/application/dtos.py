from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from src.modules.inventory.application.dtos import Unidad

Cantidad = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=3, allow_inf_nan=False)]
Bs = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False)]
CodigoLote = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]


class CosechaCreate(BaseModel):
    fecha: date
    cosechero_id: int = Field(gt=0)
    finca_id: int = Field(gt=0)
    parcela_id: int | None = Field(default=None, gt=0)
    producto_id: int = Field(gt=0)
    cantidad: Cantidad = Field(gt=0)
    monto_bs: Bs = Decimal(0)
    observacion: str | None = Field(default=None, max_length=200)

class CosechaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fecha: date
    cosechero_id: int
    finca_id: int
    parcela_id: int | None
    tipo_cosecha: str
    kg: float
    monto_bs: float
    observacion: str | None
    lote_id: int | None = None
    borrador: bool = False
    producto_id: int | None = None
    producto: str
    unidad: Unidad
    cantidad: float
    recibida: float | None
    rechazada: float | None
    motivo_rechazo: str | None
    cantidad_secundaria: float | None
    unidad_secundaria: Unidad | None
    fecha_recepcion: date | None
    documento_recepcion: str | None


class MovimientoCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    fecha: date
    detalle: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
    doc: str | None = Field(default=None, max_length=30)
    lote_id: int | None = Field(default=None, gt=0)
    finca_id: int | None = Field(default=None, gt=0)
    cantidad_entrada: Cantidad = Field(default=Decimal(0), validation_alias=AliasChoices("cantidad_entrada", "entrada_kg"))
    cantidad_salida: Cantidad = Field(default=Decimal(0), validation_alias=AliasChoices("cantidad_salida", "salida_kg"))
    observacion: str | None = Field(default=None, max_length=200)
    tipo: Literal["movimiento", "merma"] = "movimiento"
    unidad_legada: Literal["kg"] | None = Field(default=None, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def identificar_kilos(cls, data):
        if isinstance(data, dict) and any(k in data for k in ("entrada_kg", "salida_kg")):
            return {**data, "unidad_legada": "kg"}
        return data

    @model_validator(mode="after")
    def comprobar_sentido(self):
        if bool(self.cantidad_entrada) == bool(self.cantidad_salida):
            raise ValueError("Indica una cantidad positiva en entrada o en salida.")
        if self.tipo == "merma" and (not self.cantidad_salida or len((self.observacion or "").strip()) < 4):
            raise ValueError("La merma requiere una salida y una observación con el motivo.")
        return self


class MovimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fecha: date
    detalle: str
    doc: str | None
    lote_id: int | None
    finca_id: int | None
    entrada_kg: float
    salida_kg: float
    saldo_kg: float
    observacion: str | None
    cosecha_id: int | None = None
    anula_movimiento_id: int | None = None
    producto_id: int | None = None
    producto: str
    unidad: Unidad
    cantidad_entrada: float
    cantidad_salida: float
    cantidad_saldo: float
    tipo: str


class RecepcionCreate(BaseModel):
    codigo: CodigoLote
    fecha: date
    doc: str | None = Field(default=None, max_length=30)
    monto_bs: Bs | None = None
    recibida: Cantidad | None = Field(default=None, gt=0)
    rechazada: Cantidad = Decimal(0)
    motivo_rechazo: str | None = Field(default=None, max_length=200)
    cantidad_secundaria: Cantidad | None = Field(default=None, gt=0)
    unidad_secundaria: Unidad | None = None

    @model_validator(mode="after")
    def verificar_mediciones(self):
        if (self.cantidad_secundaria is None) != (self.unidad_secundaria is None):
            raise ValueError("Indica la cantidad y la unidad de la medición adicional.")
        if self.rechazada and len((self.motivo_rechazo or "").strip()) < 4:
            raise ValueError("Indica el motivo del rechazo.")
        return self


class RecepcionOut(BaseModel):
    lote_id: int
    codigo: str
    movimiento: MovimientoOut | None
    recibida: float
    rechazada: float
    aceptada: float
    unidad: Unidad


class AnulacionCreate(BaseModel):
    motivo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=200)]
