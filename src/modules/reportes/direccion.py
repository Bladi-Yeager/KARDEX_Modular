from calendar import monthrange
from datetime import date, timedelta
from functools import lru_cache
from src.modules.inventory.bitacora import informe_campo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.fechas import hoy_bolivia
from src.modules.auth.presentation.dependencies import require_roles
from src.modules.inventory.infrastructure.models_db import LoteDB
from src.modules.kardex.infrastructure.models_db import CosechaDB, MovimientoDB
from src.modules.reportes.excel import libro_excel, TIPO_EXCEL
from src.modules.reportes.finanzas import RegistroFinancieroDB, resultados_lotes

router = APIRouter(prefix="/direccion", tags=["dirección"])


def periodo(db, inicio, fin, apertura, cierre):
    m = MovimientoDB
    movimientos = db.query(m).filter(m.fecha.between(inicio, fin)).all()
    registros = db.query(RegistroFinancieroDB).filter(
        RegistroFinancieroDB.fecha.between(inicio, fin), RegistroFinancieroDB.anulado.is_(False)
    ).all()
    activos = {r.lote_id for r in movimientos + registros if r.lote_id}
    gastos_por_lote = {}
    for registro in registros:
        if registro.tipo == "costo" and registro.lote_id:
            grupo = gastos_por_lote.setdefault(registro.lote_id, {})
            concepto = registro.concepto.strip().casefold()
            grupo[concepto] = grupo.get(concepto, 0) + registro.monto_bs
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
        importes = gastos_por_lote.get(lote_id, {})
        principal = max(importes, key=importes.get) if importes else None
        filas.append(dict(gasto_principal=dict(concepto=principal, monto=importes[principal]) if principal else None,
                          codigo=actual["codigo"], producto=actual["producto"], ventas=ventas,
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


DIA = timedelta(days=1)
solo_dueno = require_roles("jefe")


def intervalo(hoy, dias, desde, hasta):
    if desde is None and hasta is None:
        return hoy - timedelta(days=dias - 1), hoy
    if (desde is None or hasta is None or desde < date(1900, 1, 1)
            or hasta > hoy or desde > hasta or (hasta - desde).days >= 366):
        raise HTTPException(422, "Elige fechas válidas hasta hoy, con un máximo de 366 días.")
    return desde, hasta


def rangos_mes(hoy, inicio=None):
    inicio = inicio or hoy.replace(day=1)
    fin_mes = inicio.replace(day=monthrange(inicio.year, inicio.month)[1])
    ultimo_previo = inicio - DIA
    if inicio <= hoy <= fin_mes:
        fin = hoy
        fin_previo = ultimo_previo.replace(day=min(hoy.day, ultimo_previo.day))
    else:
        fin, fin_previo = fin_mes, ultimo_previo
    return inicio, fin, ultimo_previo.replace(day=1), fin_previo


def calculadora(db):
    @lru_cache(maxsize=8)
    def corte(fecha):
        return {r["lote_id"]: r for r in resultados_lotes(db, fecha)}

    def calcular(inicio, fin):
        return periodo(db, inicio, fin, corte(inicio - DIA), corte(fin))

    return calcular, corte


@router.get("/mensual")
def mensual(db: Session = Depends(get_db), _actor=Depends(solo_dueno),
            anio: int | None = None, mes: int | None = None):
    hoy = hoy_bolivia()
    if (anio is None) != (mes is None):
        raise HTTPException(422, "Selecciona año y mes.")
    if anio is not None and not (1900 <= anio <= 9998 and 1 <= mes <= 12):
        raise HTTPException(422, "Año o mes fuera de rango.")
    inicio, fin, previo, fin_previo = rangos_mes(hoy, date(anio, mes, 1) if mes else None)
    if inicio > hoy:
        return dict(hoy=hoy, futuro=True, desde=inicio, hasta=fin, actual=None, anterior=None)
    datos = detalle_periodo(db, inicio, fin, previo, fin_previo)
    for periodo in (datos["actual"], datos["anterior"]):
        if not periodo["actividad"]:
            periodo["resultado"] = 0
    return dict(hoy=hoy, futuro=False, desde=inicio, hasta=fin, **datos)


@router.get("/excel-periodo")
def excel_periodo(desde: date, hasta: date, db: Session = Depends(get_db), _actor=Depends(solo_dueno)):
    intervalo(hoy_bolivia(), 1, desde, hasta)
    calcular, _ = calculadora(db)
    datos = calcular(desde, hasta)
    columnas = (("desde", "Desde"), ("hasta", "Hasta"), ("codigo", "Lote"), ("producto", "Producto"),
                ("ventas", "Ventas (Bs)"), ("costo", "Costo de salidas (Bs)"), ("gastos", "Gastos (Bs)"),
                ("resultado", "Resultado (Bs)"), ("estado", "Estado"))
    filas = [dict(f, desde=desde, hasta=hasta, estado="Pendiente" if f["resultado"] is None else "Calculado")
             for f in datos["lotes"]]
    if datos["generales"]:
        filas.append(dict(desde=desde, hasta=hasta, codigo="Gastos generales", gastos=datos["generales"],
                          resultado=-datos["generales"]))
    filas.append(dict(desde=desde, hasta=hasta, codigo="Total del período", ventas=datos["ventas"],
                      costo=datos["costo"], gastos=datos["gastos"], resultado=datos["resultado"],
                      estado="Sin actividad" if not datos["actividad"] else
                      "Pendiente" if datos["resultado"] is None else "Calculado"))
    return Response(libro_excel("Resultado por lote", columnas, filas), media_type=TIPO_EXCEL,
                    headers={"Content-Disposition": f'attachment; filename="Lotes_{desde}_{hasta}.xlsx"'})


@router.get("/resumen")
def resumen(dias: int = Query(30, ge=1, le=365), desde: date | None = None, hasta: date | None = None,
            db: Session = Depends(get_db), _actor=Depends(solo_dueno)):
    inicio, fin = intervalo(hoy_bolivia(), dias, desde, hasta)
    duracion = fin - inicio + DIA
    return detalle_periodo(db, inicio, fin, inicio - duracion, inicio - DIA)


def detalle_periodo(db, inicio, fin, previo, fin_previo):
    calcular, corte = calculadora(db)
    actual = calcular(inicio, fin)
    anterior = calcular(previo, fin_previo)
    cierre = corte(fin)
    hechos = []
    for l, c in db.query(LoteDB, CosechaDB).join(CosechaDB, LoteDB.cosecha_id==CosechaDB.id).filter(
            LoteDB.fecha_ingreso.between(inicio,fin), CosechaDB.rechazada>0):
        hechos.append(dict(fecha=l.fecha_ingreso, lote=l.codigo, tipo="Rechazo", cantidad=c.rechazada,
                           unidad=cierre[l.id]["unidad"], motivo=c.motivo_rechazo or "Sin motivo registrado"))
    m = MovimientoDB
    anulados = db.query(m.anula_movimiento_id).filter(m.anula_movimiento_id.isnot(None), m.fecha <= fin)
    for mov,l in db.query(m,LoteDB).join(LoteDB,m.lote_id==LoteDB.id).filter(
            m.fecha.between(inicio,fin),m.tipo=="merma", ~m.id.in_(anulados)):
        hechos.append(dict(fecha=mov.fecha, lote=l.codigo, tipo="Merma", cantidad=mov.cantidad_salida,
                           unidad=cierre[l.id]["unidad"], motivo=mov.observacion or "Sin motivo registrado"))
    recepciones = db.query(LoteDB).join(CosechaDB, LoteDB.cosecha_id == CosechaDB.id).filter(
        LoteDB.fecha_ingreso.between(inicio, fin), CosechaDB.recibida.isnot(None)).count()
    despachos = db.query(m).filter(m.fecha.between(inicio, fin), m.tipo == "movimiento",
                                  m.cantidad_salida > 0, ~m.id.in_(anulados)).count()
    return dict(recepciones=recepciones, despachos=despachos, campo=informe_campo(db, inicio, fin, previo, fin_previo), actual=actual, anterior=anterior, hechos=sorted(hechos,key=lambda h:h["fecha"],reverse=True),
                pendientes=[dict(codigo=l["codigo"], motivo=l["estado"]) for l in cierre.values() if l["resultado_bs"] is None])
