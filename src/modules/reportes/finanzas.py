from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, Numeric, String, false, func
from sqlalchemy.orm import Session

from src.core.database import Base, get_db
from src.modules.auth.presentation.dependencies import require_roles
from src.modules.inventory.infrastructure.models_db import FincaDB, LoteDB, ProductoDB
from src.core.fechas import hoy_bolivia
from src.modules.kardex.infrastructure.models_db import CosechaDB, MovimientoDB
from src.modules.kardex.application.dtos import AnulacionCreate, Bs

router = APIRouter(prefix="/finanzas", tags=["ventas y costos"])


class RegistroFinancieroDB(Base):
    __tablename__ = "registros_financieros"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fecha = Column(Date, nullable=False, index=True)
    tipo = Column(String(10), nullable=False)
    concepto = Column(String(150), nullable=False)
    monto_bs = Column(Numeric(12, 2), nullable=False)
    finca_id = Column(Integer, ForeignKey("fincas.id"), nullable=True)
    lote_id = Column(Integer, ForeignKey("lotes.id"), nullable=True, index=True)
    registrado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    anulado = Column(Boolean, nullable=False, server_default=false())
    anulado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    motivo_anulacion = Column(String(200), nullable=True)


class RegistroCreate(BaseModel):
    fecha: date
    tipo: Literal["venta", "costo", "compra"]
    concepto: str = Field(min_length=3, max_length=150)
    monto_bs: Bs = Field(gt=0)
    finca_id: int | None = Field(default=None, gt=0)


    lote_id: int | None = Field(default=None, gt=0)


class RegistroOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fecha: date
    tipo: str
    concepto: str
    monto_bs: float
    finca_id: int | None
    lote_id: int | None
    anulado: bool
    motivo_anulacion: str | None


def registros(db, finca_id=None):
    consulta = db.query(RegistroFinancieroDB)
    if finca_id is not None:
        consulta = consulta.filter(RegistroFinancieroDB.finca_id == finca_id)
    return consulta.order_by(RegistroFinancieroDB.fecha, RegistroFinancieroDB.id)


def resultado_registrado(db, desde, hasta, finca_id):
    filas = registros(db, finca_id).filter(
        RegistroFinancieroDB.fecha.between(desde, hasta),
        RegistroFinancieroDB.anulado.is_(False),
    ).all()
    ventas = [r.monto_bs for r in filas if r.tipo == "venta"]
    costos = [r.monto_bs for r in filas if r.tipo in ("costo", "compra")]
    compras = db.query(CosechaDB.monto_bs).join(LoteDB, LoteDB.cosecha_id == CosechaDB.id).filter(
        LoteDB.fecha_ingreso.between(desde, hasta), CosechaDB.monto_bs > 0)
    if finca_id is not None:
        compras = compras.filter(LoteDB.finca_id == finca_id)
    costos.extend(monto for (monto,) in compras)
    return {
        "ventas_bs": sum(ventas),
        "costos_bs": sum(costos),
        "resultado_bs": sum(ventas) - sum(costos) if ventas and costos else None,
    }


def resultados_lotes(db, corte, finca_id=None):
    lotes = db.query(LoteDB, CosechaDB, ProductoDB).outerjoin(
        CosechaDB, LoteDB.cosecha_id == CosechaDB.id
    ).outerjoin(ProductoDB, LoteDB.producto_id == ProductoDB.id).filter(LoteDB.fecha_ingreso <= corte)
    if finca_id is not None:
        lotes = lotes.filter(LoteDB.finca_id == finca_id)
    m = MovimientoDB
    existencias = dict(db.query(m.lote_id, func.sum(
        func.coalesce(m.cantidad_entrada, m.entrada_kg) - func.coalesce(m.cantidad_salida, m.salida_kg)
    )).filter(m.fecha <= corte).group_by(m.lote_id).all())
    r = RegistroFinancieroDB
    importes = {(lote, tipo): monto for lote, tipo, monto in db.query(
        r.lote_id, r.tipo, func.sum(r.monto_bs)
    ).filter(r.fecha <= corte, r.anulado.is_(False), r.lote_id.isnot(None)).group_by(r.lote_id, r.tipo)}
    filas = []
    for lote, cosecha, producto in lotes.order_by(LoteDB.fecha_ingreso.desc(), LoteDB.codigo):
        saldo = existencias.get(lote.id, Decimal(0))
        cantidad = cosecha.cantidad if cosecha else None
        compra = (cosecha.monto_bs if cosecha else None) or importes.get((lote.id, "compra"))
        ventas = importes.get((lote.id, "venta"), Decimal(0))
        gastos = importes.get((lote.id, "costo"), Decimal(0))
        aplicado = resultado = None
        if cantidad == 0 and saldo == 0:
            estado = "Recepción rechazada"
            aplicado = Decimal(0)
        elif compra is None:
            estado = "Falta importe de compra"
        elif saldo == 0 or (cantidad and 0 <= saldo <= cantidad):
            proporcion = (cantidad - saldo) / cantidad if saldo else Decimal(1)
            aplicado = (compra * proporcion).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            estado = "Con existencias" if saldo else "Sin existencias"
        else:
            estado = "Falta cantidad de recepción"
        if aplicado is not None:
            resultado = ventas - aplicado - gastos
        filas.append(dict(lote_id=lote.id, codigo=lote.codigo, producto=producto.nombre if producto else "Histórico",
                          unidad=producto.unidad if producto else "kg", saldo=saldo, compra_bs=compra,
                          costo_salidas_bs=aplicado, ventas_bs=ventas, gastos_bs=gastos,
                          resultado_bs=resultado, estado=estado))
    return filas


@router.get("/lotes")
def por_lote(hasta: date | None = None, finca_id: int | None = None,
             db: Session = Depends(get_db), _actor=Depends(require_roles("jefe"))):
    return resultados_lotes(db, hasta or hoy_bolivia(), finca_id)


@router.get("", response_model=list[RegistroOut])
def listar(db: Session = Depends(get_db), _actor=Depends(require_roles("admin"))):
    return registros(db).all()


@router.post("", response_model=RegistroOut, status_code=201)
def registrar(data: RegistroCreate, db: Session = Depends(get_db), actor=Depends(require_roles("admin"))):
    if data.monto_bs <= 0 or len(data.concepto.strip()) < 3:
        raise HTTPException(422, "Indica un monto positivo y un concepto de al menos tres caracteres.")
    if data.lote_id is None and data.tipo in ("venta", "compra"):
        raise HTTPException(422, "Selecciona el lote para esta operación.")
    if data.lote_id is not None:
        lote = db.get(LoteDB, data.lote_id, with_for_update=True)
        if lote is None or data.fecha < lote.fecha_ingreso:
            raise HTTPException(422, "El lote debe existir en la fecha del registro.")
        if data.finca_id is not None and data.finca_id != lote.finca_id:
            raise HTTPException(422, "La finca indicada no corresponde al lote.")
        data.finca_id = lote.finca_id
        cosecha = db.get(CosechaDB, lote.cosecha_id) if lote.cosecha_id else None
        if data.tipo in ("venta", "compra") and cosecha and cosecha.cantidad == 0:
            raise HTTPException(422, "Esta recepción fue rechazada por completo.")
        if data.tipo == "compra":
            existente = db.query(RegistroFinancieroDB.id).filter_by(lote_id=lote.id, tipo="compra", anulado=False).first()
            if (cosecha and cosecha.monto_bs) or existente:
                raise HTTPException(409, "El lote ya tiene un importe de compra.")
    elif data.finca_id is not None:
        finca = db.get(FincaDB, data.finca_id)
        if finca is None or not finca.activo:
            raise HTTPException(422, "Selecciona una finca activa.")
    row = RegistroFinancieroDB(**data.model_dump(), registrado_por=actor.id)
    row.concepto = row.concepto.strip()
    db.add(row)
    db.commit()
    return row


@router.post("/{registro_id}/anular", response_model=RegistroOut)
def anular(registro_id: int, data: AnulacionCreate, db: Session = Depends(get_db), actor=Depends(require_roles("admin"))):
    row = db.get(RegistroFinancieroDB, registro_id, with_for_update=True)
    if row is None:
        raise HTTPException(404, "Registro financiero no encontrado.")
    if row.anulado:
        raise HTTPException(409, "El registro ya está anulado.")
    row.anulado = True
    row.anulado_por = actor.id
    row.motivo_anulacion = data.motivo
    db.commit()
    return row
