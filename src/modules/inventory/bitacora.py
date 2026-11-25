from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.database import Base, get_db
from src.core.fechas import hoy_bolivia
from src.modules.auth.presentation.dependencies import require_roles
from src.modules.inventory.infrastructure.models_db import FincaDB, LoteDB, ParcelaDB, ProductoDB
from src.modules.kardex.infrastructure.models_db import CosechaDB

router = APIRouter(prefix="/bitacora", tags=["bitácora por parcela"])


class EntradaDB(Base):
    __tablename__ = "bitacora_parcela"
    id = Column(Integer, primary_key=True)
    parcela_id = Column(Integer, ForeignKey("parcelas.id"), nullable=False, index=True)
    fecha = Column(Date, nullable=False, index=True)
    tipo = Column(String(16), nullable=False)
    detalle = Column(String(250), nullable=False)
    insumo = Column(String(100))
    dosis = Column(Numeric(12, 3))
    unidad_dosis = Column(String(16))
    cosecha_id = Column(Integer, ForeignKey("cosechas.id"), unique=True)
    area_ha = Column(Numeric(10, 4))
    autor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)


class Entrada(BaseModel):
    parcela_id: int = Field(gt=0)
    fecha: date
    tipo: Literal["Abono", "Cosecha", "Incidencia"]
    detalle: str = Field(min_length=3, max_length=250)
    insumo: str | None = Field(None, max_length=100)
    dosis: Decimal | None = Field(None, gt=0, max_digits=12, decimal_places=3)
    unidad_dosis: Literal["kg/ha", "L/ha", "g/planta", "mL/planta"] | None = None
    cosecha_id: int | None = Field(None, gt=0)
    area_ha: Decimal | None = Field(None, gt=0, max_digits=10, decimal_places=4)


@router.post("", status_code=201)
def guardar(data: Entrada, db: Session = Depends(get_db), actor=Depends(require_roles("admin"))):
    parcela = db.get(ParcelaDB, data.parcela_id)
    if not parcela or not parcela.activo or not db.get(FincaDB, parcela.finca_id).activo:
        raise HTTPException(422, "Selecciona una parcela activa.")
    if data.fecha > hoy_bolivia() or len(data.detalle.strip()) < 3:
        raise HTTPException(422, "Revisa la fecha y describe lo observado.")
    registro = EntradaDB(parcela_id=parcela.id, fecha=data.fecha, tipo=data.tipo,
                         detalle=data.detalle.strip(), autor_id=actor.id)
    if data.tipo == "Abono":
        if not (data.insumo or "").strip() or not data.dosis or not data.unidad_dosis:
            raise HTTPException(422, "Indica el abono, la dosis y su unidad.")
        registro.insumo, registro.dosis, registro.unidad_dosis = data.insumo.strip(), data.dosis, data.unidad_dosis
    if data.tipo == "Cosecha":
        c = db.get(CosechaDB, data.cosecha_id) if data.cosecha_id else None
        if not c or c.parcela_id != parcela.id or c.borrador or c.recibida is None or c.fecha != data.fecha:
            raise HTTPException(422, "Elige una cosecha recibida de esta parcela y usa su fecha de cosecha.")
        if not data.area_ha or (parcela.superficie_ha and data.area_ha > parcela.superficie_ha):
            raise HTTPException(422, "Verifica la superficie efectivamente cosechada.")
        registro.cosecha_id, registro.area_ha = c.id, data.area_ha
    db.add(registro)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "La cosecha ya tiene un registro de superficie.") from error
    return {"id": registro.id}


def registros(db, desde=None, hasta=None):
    q = db.query(EntradaDB, ParcelaDB, FincaDB, CosechaDB, ProductoDB, LoteDB).join(
        ParcelaDB, EntradaDB.parcela_id == ParcelaDB.id).join(FincaDB, ParcelaDB.finca_id == FincaDB.id
    ).outerjoin(CosechaDB, EntradaDB.cosecha_id == CosechaDB.id
    ).outerjoin(ProductoDB, CosechaDB.producto_id == ProductoDB.id
    ).outerjoin(LoteDB, CosechaDB.id == LoteDB.cosecha_id)
    if desde:
        q = q.filter(EntradaDB.fecha >= desde)
    if hasta:
        q = q.filter(EntradaDB.fecha <= hasta)
    return [dict(id=e.id, fecha=e.fecha, tipo=e.tipo, parcela_id=p.id, parcela=f"{f.nombre or f.numero} · Parcela {p.numero}",
                 detalle=e.detalle, insumo=e.insumo, dosis=e.dosis, unidad_dosis=e.unidad_dosis, cosecha_id=e.cosecha_id,
                 area_ha=e.area_ha, producto_id=c.producto_id if c else None, producto=pr.nombre if pr else None,
                 unidad=pr.unidad if pr else None, aceptada=c.cantidad if c else None, lote=l.codigo if l else None)
            for e,p,f,c,pr,l in q.order_by(EntradaDB.fecha.desc(), EntradaDB.id.desc())]


@router.get("")
def historial(db: Session = Depends(get_db), _actor=Depends(require_roles("admin"))):
    return registros(db)


def informe_campo(db, inicio, fin):
    previo = inicio - (fin-inicio+timedelta(days=1))
    filas = registros(db, previo, fin)
    grupos = {}
    for fila in filas:
        if fila["tipo"] != "Cosecha":
            continue
        clave = (fila["parcela_id"], fila["producto_id"])
        grupo = grupos.setdefault(clave, dict(parcela=fila["parcela"], producto=fila["producto"], unidad=fila["unidad"],
                                              actual=[0,0], anterior=[0,0]))
        total = grupo["actual" if fila["fecha"] >= inicio else "anterior"]
        total[0] += fila["aceptada"]
        total[1] += fila["area_ha"]
    for grupo in grupos.values():
        for periodo in ("actual","anterior"):
            cantidad, area = grupo[periodo]
            grupo[periodo] = cantidad / area if area else None
        a,b = grupo["actual"],grupo["anterior"]
        grupo["cambio_pct"] = (a-b)*100/b if a is not None and b else None
    return dict(rendimientos=list(grupos.values()), actividades=[f for f in filas if f["fecha"] >= inicio])
