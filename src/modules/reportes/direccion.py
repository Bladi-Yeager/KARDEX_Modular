from datetime import timedelta
from src.modules.inventory.bitacora import informe_campo

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.fechas import hoy_bolivia
from src.modules.auth.presentation.dependencies import require_roles
from src.modules.inventory.infrastructure.models_db import LoteDB
from src.modules.kardex.infrastructure.models_db import CosechaDB, MovimientoDB
from src.modules.reportes.finanzas import RegistroFinancieroDB, resultados_lotes

router = APIRouter(prefix="/direccion", tags=["dirección"])


def periodo(db, inicio, fin, apertura, cierre):
    m = MovimientoDB
    movimientos = db.query(m).filter(m.fecha.between(inicio, fin)).all()
    registros = db.query(RegistroFinancieroDB).filter(
        RegistroFinancieroDB.fecha.between(inicio, fin), RegistroFinancieroDB.anulado.is_(False)
    ).all()
    activos = {r.lote_id for r in movimientos + registros if r.lote_id}
    filas = []
    for lote_id in sorted(activos):
        if lote_id not in cierre:
            continue
        actual = cierre[lote_id]
        anterior = apertura.get(lote_id, {})
        costo = actual["costo_salidas_bs"]
        previo = anterior.get("costo_salidas_bs", 0)
        costo = costo - previo if costo is not None and previo is not None else None
        ventas = actual["ventas_bs"] - anterior.get("ventas_bs", 0)
        gastos = actual["gastos_bs"] - anterior.get("gastos_bs", 0)
        filas.append(dict(codigo=actual["codigo"], producto=actual["producto"], ventas=ventas,
                          gastos=gastos, costo=costo, resultado=None if costo is None else ventas-gastos-costo))
    ventas = sum(f["ventas"] for f in filas) + sum(r.monto_bs for r in registros if not r.lote_id and r.tipo=="venta")
    generales = sum(r.monto_bs for r in registros if not r.lote_id and r.tipo=="costo")
    gastos = generales + sum(f["gastos"] for f in filas)
    costo = None if any(f["costo"] is None for f in filas) else sum(f["costo"] for f in filas)
    conceptos = {}
    for registro in registros:
        if registro.tipo == "costo":
            clave = registro.concepto.strip().casefold()
            conceptos[clave] = conceptos.get(clave, 0) + registro.monto_bs
    actividad = bool(filas or registros)
    return dict(desde=inicio, hasta=fin, ventas=ventas, gastos=gastos, generales=generales, costo=costo,
                resultado=ventas-gastos-costo if actividad and costo is not None else None,
                actividad=actividad, lotes=filas, conceptos=conceptos)


@router.get("/resumen")
def resumen(dias: int = Query(30, ge=1, le=365), db: Session = Depends(get_db), _actor=Depends(require_roles("jefe"))):
    hoy = hoy_bolivia()
    duracion = timedelta(days=dias)
    ayer = timedelta(days=1)
    inicio = hoy - duracion + ayer
    def corte(fecha):
        return {r["lote_id"]: r for r in resultados_lotes(db, fecha)}
    intermedio = corte(inicio - ayer)
    cierre = corte(hoy)
    actual = periodo(db, inicio, hoy, intermedio, cierre)
    anterior = periodo(db, inicio-duracion, inicio-ayer, corte(inicio-duracion-ayer), intermedio)
    hechos = []
    for l, c in db.query(LoteDB, CosechaDB).join(CosechaDB, LoteDB.cosecha_id==CosechaDB.id).filter(
            LoteDB.fecha_ingreso.between(inicio,hoy), CosechaDB.rechazada>0):
        hechos.append(dict(fecha=l.fecha_ingreso, lote=l.codigo, tipo="Rechazo", cantidad=c.rechazada,
                           unidad=cierre[l.id]["unidad"], motivo=c.motivo_rechazo or "Sin motivo registrado"))
    m = MovimientoDB
    anulados = db.query(m.anula_movimiento_id).filter(m.anula_movimiento_id.isnot(None), m.fecha <= hoy)
    for mov,l in db.query(m,LoteDB).join(LoteDB,m.lote_id==LoteDB.id).filter(
            m.fecha.between(inicio,hoy),m.tipo=="merma", ~m.id.in_(anulados)):
        hechos.append(dict(fecha=mov.fecha, lote=l.codigo, tipo="Merma", cantidad=mov.cantidad_salida,
                           unidad=cierre[l.id]["unidad"], motivo=mov.observacion or "Sin motivo registrado"))
    return dict(campo=informe_campo(db, inicio, hoy), actual=actual, anterior=anterior, hechos=sorted(hechos,key=lambda h:h["fecha"],reverse=True),
                pendientes=[dict(codigo=l["codigo"], motivo=l["estado"]) for l in cierre.values() if l["resultado_bs"] is None])
