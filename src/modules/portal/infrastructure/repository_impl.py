"""Consultas de SOLO LECTURA del portal del productor.

Todas las consultas filtran por el usuario dueno del token. Un productor
nunca puede ver fincas, cosechas ni movimientos de otro productor.
"""

from typing import List

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from src.modules.inventory.infrastructure.models_db import FincaDB, LoteDB, ParcelaDB, ProductoDB
from src.modules.kardex.infrastructure.models_db import CosechaDB, MovimientoDB
from src.modules.kardex.domain.saldos import acumular_por_producto, datos_producto
from src.modules.kardex.infrastructure.repository_impl import datos_movimiento, datos_recepcion, finca_del_movimiento
from src.modules.portal.domain.models import (
    CosechaDelProductor,
    FincaDelProductor,
    LoteDelProductor,
    MovimientoDelProductor,
)
from src.modules.supliers.infrastructure.models_db import CosecheroDB


class PortalRepositoryImpl:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ ayudas
    def _mis_fincas(self, usuario_id: int) -> List[int]:
        filas = (
            self.db.query(FincaDB.id)
            .filter(FincaDB.usuario_id == usuario_id)
            .all()
        )
        return [f[0] for f in filas]

    # ------------------------------------------------------------------ fincas
    def fincas(self, usuario_id: int) -> List[FincaDelProductor]:
        filas = (
            self.db.query(FincaDB)
            .filter(FincaDB.usuario_id == usuario_id)
            .order_by(FincaDB.numero)
            .all()
        )
        if not filas:
            return []

        ids = [f.id for f in filas]
        conteo = {
            finca_id: (n, ha)
            for finca_id, n, ha in self.db.query(
                ParcelaDB.finca_id,
                func.count(ParcelaDB.id),
                func.coalesce(func.sum(ParcelaDB.superficie_ha), 0),
            )
            .filter(ParcelaDB.finca_id.in_(ids))
            .group_by(ParcelaDB.finca_id)
            .all()
        }

        resultado = []
        for f in filas:
            n, ha = conteo.get(f.id, (0, 0))
            resultado.append(
                FincaDelProductor(
                    id=f.id,
                    numero=f.numero,
                    nombre=f.nombre,
                    ubicacion=f.ubicacion,
                    parcelas=int(n or 0),
                    hectareas=round(float(ha or 0), 2),
                )
            )
        return resultado

    # ------------------------------------------------------------------ cosechas
    def cosechas(self, usuario_id: int) -> List[CosechaDelProductor]:
        fincas = self._mis_fincas(usuario_id)
        if not fincas:
            return []

        filas = (
            self.db.query(CosechaDB, FincaDB, ParcelaDB, CosecheroDB, ProductoDB, LoteDB)
            .outerjoin(FincaDB, CosechaDB.finca_id == FincaDB.id)
            .outerjoin(ParcelaDB, and_(CosechaDB.parcela_id == ParcelaDB.id, CosechaDB.finca_id == ParcelaDB.finca_id))
            .outerjoin(CosecheroDB, CosechaDB.cosechero_id == CosecheroDB.id)
            .outerjoin(ProductoDB, CosechaDB.producto_id == ProductoDB.id)
            .outerjoin(LoteDB, LoteDB.cosecha_id == CosechaDB.id)
            .filter(CosechaDB.finca_id.in_(fincas), CosechaDB.borrador.is_(False))
            .order_by(CosechaDB.fecha.desc(), CosechaDB.id.desc())
            .all()
        )

        resultado = []
        for cosecha, finca, parcela, cosechero, producto, lote in filas:
            resultado.append(
                CosechaDelProductor(
                    id=cosecha.id,
                    fecha=cosecha.fecha,
                    finca=finca.nombre if finca else None,
                    parcela=f"Parcela {parcela.numero}" if parcela else None,
                    cosechero=cosechero.nombre if cosechero else None,
                    tipo_cosecha=cosecha.tipo_cosecha,
                    kg=float(cosecha.kg or 0),
                    monto_bs=float(cosecha.monto_bs or 0),
                    observacion=cosecha.observacion,
                    codigo_lote=lote.codigo if lote else None,
                    **datos_producto(producto),
                    **datos_recepcion(cosecha, lote),
                )
            )
        return resultado

    # ------------------------------------------------------------------ kardex
    def movimientos(self, usuario_id: int) -> List[MovimientoDelProductor]:
        fincas = self._mis_fincas(usuario_id)
        if not fincas:
            return []

        finca_visible = finca_del_movimiento()
        filas = (
            self.db.query(MovimientoDB, FincaDB, LoteDB, ProductoDB)
            .outerjoin(LoteDB, MovimientoDB.lote_id == LoteDB.id)
            .join(FincaDB, finca_visible == FincaDB.id)
            .outerjoin(ProductoDB, LoteDB.producto_id == ProductoDB.id)
            .filter(FincaDB.usuario_id == usuario_id)
            .order_by(MovimientoDB.fecha.asc(), MovimientoDB.id.asc())
            .all()
        )

        resultado = []
        saldos = acumular_por_producto((mov, producto.id if producto else None) for mov, _, _, producto in filas)
        for (mov, finca, lote, producto), saldo in zip(filas, saldos):
            resultado.append(
                MovimientoDelProductor(
                    id=mov.id,
                    fecha=mov.fecha,
                    detalle=mov.detalle,
                    doc=mov.doc,
                    lote=lote.codigo if lote else None,
                    finca=finca.nombre if finca else None,
                    observacion=mov.observacion,
                    anula_movimiento_id=mov.anula_movimiento_id,
                    **datos_movimiento(mov, producto, saldo),
                )
            )
        return resultado

    # ------------------------------------------------------------------ lotes
    def lotes(self, usuario_id: int) -> List[LoteDelProductor]:
        fincas = self._mis_fincas(usuario_id)
        if not fincas:
            return []

        filas = (
            self.db.query(LoteDB, FincaDB, ProductoDB)
            .outerjoin(FincaDB, LoteDB.finca_id == FincaDB.id)
            .outerjoin(ProductoDB, LoteDB.producto_id == ProductoDB.id)
            .filter(LoteDB.finca_id.in_(fincas))
            .order_by(LoteDB.fecha_ingreso.desc())
            .all()
        )
        return [
            LoteDelProductor(
                id=lote.id,
                codigo=lote.codigo,
                finca=finca.nombre if finca else None,
                fecha_ingreso=lote.fecha_ingreso,
                detalle=lote.detalle,
                cosecha_id=lote.cosecha_id,
                **datos_producto(producto),
            )
            for lote, finca, producto in filas
        ]
