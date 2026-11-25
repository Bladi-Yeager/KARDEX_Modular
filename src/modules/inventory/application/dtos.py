from datetime import date
from typing import Annotated, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Unidad = Literal["kg", "unidad", "caja"]


class ProductoCreate(BaseModel):
    nombre: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=70)]
    unidad: Unidad


class ProductoOut(ProductoCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class FincaCreate(BaseModel):
    numero: int
    nombre: Optional[str] = None
    ubicacion: Optional[str] = None
    usuario_id: Optional[int] = None


class FincaOut(FincaCreate):
    id: int
    activo: bool

    class Config:
        from_attributes = True


class FincaAsignar(BaseModel):
    usuario_id: Optional[int] = None


class ParcelaCreate(BaseModel):
    finca_id: int
    numero: int
    superficie_ha: Optional[float] = None


class ParcelaOut(ParcelaCreate):
    id: int
    activo: bool

    class Config:
        from_attributes = True


class LoteCreate(BaseModel):
    codigo: str
    finca_id: Optional[int] = None
    fecha_ingreso: date
    detalle: Optional[str] = None
    producto_id: int = Field(gt=0)


class LoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    finca_id: Optional[int] = None
    fecha_ingreso: date
    detalle: Optional[str] = None
    cosecha_id: Optional[int] = None
    producto_id: Optional[int] = None
    producto: str = "Histórico sin clasificar"
    unidad: Unidad = "kg"
