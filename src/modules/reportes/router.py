from datetime import date, datetime, timedelta, timezone
from unicodedata import category, normalize

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.modules.inventory.bitacora import registros as registros_campo
from src.core.database import get_db
from src.core.fechas import hoy_bolivia
from src.modules.auth.domain.models import rol_efectivo
from src.modules.auth.infrastructure.repository_impl import UsuarioRepositoryImpl
from src.modules.auth.presentation.dependencies import get_current_user, require_roles
from src.modules.inventory.infrastructure.repository_impl import FincaRepositoryImpl, LoteRepositoryImpl, ParcelaRepositoryImpl
from src.modules.inventory.infrastructure.models_db import ProductoDB
from src.modules.kardex.infrastructure.repository_impl import CosechaRepositoryImpl, MovimientoRepositoryImpl
from src.modules.kardex.domain.saldos import resumen_por_producto
from src.modules.portal.application.services import PortalService
from src.modules.portal.infrastructure.repository_impl import PortalRepositoryImpl
from src.modules.reportes.excel import TIPO_EXCEL, libro_excel
from src.modules.reportes.finanzas import registros, resultados_lotes
from src.modules.supliers.infrastructure.repository_impl import CosecheroRepositoryImpl

router = APIRouter(prefix="/reportes", tags=["reportes"])
operador = require_roles("admin")

FINCAS = (("numero", "Número"), ("nombre", "Finca"), ("ubicacion", "Ubicación"))
COSECHAS = (("fecha", "Fecha de cosecha"), ("fecha_recepcion", "Fecha de recepción"), ("finca", "Finca"),
            ("parcela", "Parcela"), ("cosechero", "Cosechero"), ("producto", "Producto"), ("unidad", "Unidad"),
            ("codigo_lote", "Lote"), ("documento_recepcion", "Documento"), ("recibida", "Recibida"),
            ("rechazada", "Rechazada"), ("cantidad", "Cantidad registrada"), ("motivo_rechazo", "Motivo del rechazo"),
            ("unidad_secundaria", "Unidad adicional"), ("cantidad_secundaria", "Medición adicional"),
            ("monto_bs", "Monto registrado (Bs)"), ("observacion", "Observación"))
LOTES = (("codigo", "Código de lote"), ("finca", "Finca"), ("fecha_ingreso", "Fecha de ingreso"),
         ("producto", "Producto"), ("unidad", "Unidad"), ("detalle", "Detalle"), ("cosecha_id", "N.º de cosecha"))
KARDEX = (("fecha", "Fecha"), ("detalle", "Detalle"), ("tipo", "Tipo"), ("doc", "Documento"),
          ("finca", "Finca"), ("lote", "Lote"), ("producto", "Producto"), ("unidad", "Unidad"),
          ("cantidad_entrada", "Entrada"), ("cantidad_salida", "Salida"), ("cantidad_saldo", "Saldo"),
          ("observacion", "Observación"))
EXISTENCIAS = (("desde", "Inicio"), ("hasta", "Corte"), ("producto", "Producto"), ("unidad", "Unidad"),
               ("apertura", "Saldo inicial"), ("recibida", "Recibida"), ("rechazada", "Rechazada"),
               ("entrada", "Entradas al Kardex"), ("salida", "Salidas del Kardex (incluye mermas)"),
               ("merma", "Merma neta"), ("saldo", "Saldo al cierre"))
ESTADO = (("componente", "Componente"), ("estado", "Estado"), ("revision", "Verificado"))
CUENTAS = (("username", "Usuario"), ("nombre_completo", "Nombre"), ("rol", "Rol"), ("activo", "Activo"))


def _texto(valor):
    return "".join(letra for letra in normalize("NFD", str(valor).lower()) if category(letra) != "Mn")


def _periodo(desde, hasta):
    if desde is not None and hasta is not None and desde > hasta:
        raise HTTPException(422, "La fecha inicial debe ser anterior o igual a la final.")


def _filtrar(filas, columnas, desde, hasta, buscar, tabla, producto_id):
    needle = _texto(buscar.strip())
    campos_busqueda = {
        "cosechas": ("finca", "parcela", "cosechero", "producto", "observacion"),
        "kardex": ("detalle", "doc", "lote", "finca", "producto", "observacion"),
        "lotes": ("codigo", "finca", "producto", "detalle"),
    }
    campos = campos_busqueda.get(tabla, [campo for campo, _ in columnas])
    for fila in filas:
        fecha = fila.get("fecha_recepcion") or fila.get("fecha") or fila.get("fecha_ingreso")
        if fecha and ((desde and fecha < desde) or (hasta and fecha > hasta)):
            continue
        if producto_id is not None and (fila.get("producto_id") or 0) != producto_id:
            continue
        if needle and needle not in _texto(" ".join(str(fila.get(campo) or "") for campo in campos)):
            continue
        yield fila


def _fincas(db):
    return {f.id: f.nombre or f"Finca {f.numero}" for f in FincaRepositoryImpl(db).list_all()}


def _datos_empresa(db, tabla, finca_id, lote_id, confirmadas):
    fincas = _fincas(db)
    if tabla == "fincas":
        return FINCAS, [vars(f) for f in FincaRepositoryImpl(db).list_all() if not finca_id or f.id == finca_id]
    if tabla == "parcelas":
        columnas = (("finca", "Finca"), ("numero", "Número de parcela"), ("superficie_ha", "Superficie (ha)"))
        return columnas, [dict(vars(p), finca=fincas.get(p.finca_id)) for p in ParcelaRepositoryImpl(db).list_all()
                          if not finca_id or p.finca_id == finca_id]
    lotes = LoteRepositoryImpl(db).list_all()
    if tabla == "lotes":
        return LOTES, [dict(vars(l), finca=fincas.get(l.finca_id)) for l in lotes
                       if not finca_id or l.finca_id == finca_id]
    if tabla == "kardex":
        codigos = {l.id: l.codigo for l in lotes}
        return KARDEX, [dict(vars(m), finca=fincas.get(m.finca_id), lote=codigos.get(m.lote_id))
                        for m in MovimientoRepositoryImpl(db).list_all(finca_id, lote_id)]
    cosecheros = {c.id: c.nombre for c in CosecheroRepositoryImpl(db).list_all()}
    parcelas = {p.id: p.numero for p in ParcelaRepositoryImpl(db).list_all()}
    codigos = {l.id: l.codigo for l in lotes}
    return COSECHAS, [dict(vars(c), finca=fincas.get(c.finca_id), cosechero=cosecheros.get(c.cosechero_id),
                           codigo_lote=codigos.get(c.lote_id),
                           parcela=parcelas.get(c.parcela_id)) for c in CosechaRepositoryImpl(db).list_all()
                      if (not finca_id or c.finca_id == finca_id) and (not confirmadas or not c.borrador)]


def _datos_productor(db, actor, tabla):
    servicio = PortalService(PortalRepositoryImpl(db))
    opciones = {
        "fincas": (FINCAS + (("parcelas", "Parcelas"), ("hectareas", "Superficie (ha)")), servicio.fincas),
        "cosechas": (COSECHAS, servicio.cosechas),
        "lotes": (LOTES, servicio.lotes),
        "kardex": (KARDEX, servicio.movimientos),
    }
    if tabla not in opciones:
        raise HTTPException(403, "Esta tabla no está disponible para tu perfil.")
    columnas, consultar = opciones[tabla]
    return columnas, [r.model_dump() for r in consultar(actor)]


def _diagnostico(db):
    db.execute(text("SELECT 1"))
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    return [{"componente": "API", "estado": "Disponible", "revision": ahora},
            {"componente": "Base de datos", "estado": "Con conexión", "revision": ahora}]


@router.get("/diagnostico")
def diagnostico(db: Session = Depends(get_db), _actor=Depends(require_roles("soporte"))):
    return _diagnostico(db)


def _datos_excel(db, actor, tabla, finca_id, lote_id, confirmadas):
    if actor.rol == "cliente":
        return _datos_productor(db, actor, tabla)
    if actor.rol == "soporte" and tabla == "diagnostico":
        return ESTADO, _diagnostico(db)
    if actor.rol == "admin":
        if tabla == "productos":
            columnas = (("producto", "Producto"), ("unidad", "Unidad de inventario"))
            filas = db.query(ProductoDB).order_by(ProductoDB.nombre, ProductoDB.unidad).all()
            return columnas, [{"producto": p.nombre, "unidad": p.unidad} for p in filas]
        if tabla in ("fincas", "parcelas", "lotes", "kardex", "cosechas"):
            return _datos_empresa(db, tabla, finca_id, lote_id, confirmadas)
        if tabla == "bitacora":
            columnas = (("fecha","Fecha"),("parcela","Parcela"),("tipo","Actividad"),("detalle","Descripción"),
                        ("insumo","Abono"),("dosis","Dosis"),("unidad_dosis","Unidad de dosis"),("lote","Lote"),
                        ("area_ha","Superficie cosechada (ha)"),("aceptada","Aceptada"),("unidad","Unidad"))
            return columnas, registros_campo(db)
        if tabla == "cuentas":
            rol = "cliente"
            return CUENTAS, [dict(vars(u), rol=rol) for u in UsuarioRepositoryImpl(db).list_all()
                             if rol_efectivo(u.rol) == rol]
        if tabla == "finanzas":
            fincas = _fincas(db)
            codigos = {l.id: l.codigo for l in LoteRepositoryImpl(db).list_all()}
            columnas = (("fecha", "Fecha"), ("tipo", "Tipo"), ("concepto", "Concepto"), ("finca", "Finca"),
                        ("lote", "Lote"), ("monto_bs", "Monto (Bs)"), ("estado", "Estado"), ("motivo", "Motivo de anulación"))
            return columnas, [
                {"fecha": row.fecha, "tipo": row.tipo, "concepto": row.concepto,
                 "lote": codigos.get(row.lote_id, "Sin lote"), "finca": fincas.get(row.finca_id), "monto_bs": float(row.monto_bs),
                 "estado": "Anulado" if row.anulado else "Vigente", "motivo": row.motivo_anulacion}
                for row in registros(db, finca_id)
            ]
        if actor.rol == "admin" and tabla == "afiliaciones":
            servicio = PortalService(PortalRepositoryImpl(db))
            columnas = (("productor", "Productor"), ("usuario", "Usuario"), ("fincas", "Fincas asociadas"))
            return columnas, [
                {"productor": c.nombre_completo, "usuario": c.username,
                 "fincas": ", ".join(f.nombre or f"Finca {f.numero}" for f in c.fincas)}
                for c in servicio.clientes(UsuarioRepositoryImpl(db))
            ]
        if actor.rol == "admin" and tabla == "cosecheros":
            columnas = (("nombre", "Nombre"), ("ci", "Documento"), ("telefono", "Teléfono"), ("activo", "Activo"))
            return columnas, [vars(c) for c in CosecheroRepositoryImpl(db).list_all()]
    raise HTTPException(403, "Esta tabla no está disponible para tu perfil.")


@router.get("/excel/{tabla}")
def descargar_excel(tabla: str, fecha_desde: date | None = None, fecha_hasta: date | None = None,
                    finca_id: int | None = Query(None, gt=0), buscar: str = Query("", max_length=160),
                    lote_id: int | None = Query(None, gt=0),
                    producto_id: int | None = Query(None, ge=0),
                    confirmadas: bool = False,
                    db: Session = Depends(get_db), actor=Depends(get_current_user)):
    _periodo(fecha_desde, fecha_hasta)
    if tabla == "resultado-lotes" and actor.rol == "jefe":
        corte = fecha_hasta or hoy_bolivia()
        filas = [dict(fila, corte=corte) for fila in resultados_lotes(db, corte, finca_id)]
        columnas = (("corte", "Acumulado al"), ("codigo", "Lote"), ("producto", "Producto"), ("unidad", "Unidad"),
                    ("saldo", "Existencias"), ("ventas_bs", "Ventas (Bs)"), ("compra_bs", "Compra total (Bs)"),
                    ("costo_salidas_bs", "Costo de salidas y mermas (Bs)"), ("gastos_bs", "Otros gastos (Bs)"),
                    ("resultado_bs", "Resultado registrado (Bs)"), ("estado", "Estado"))
    elif tabla == "existencias" and actor.rol == "admin":
        reporte = _resumen(db, fecha_desde, fecha_hasta, finca_id)
        columnas = EXISTENCIAS
        filas = [dict(fila, desde=reporte["desde"], hasta=reporte["hasta"]) for fila in reporte["existencias"]]
    else:
        columnas, filas = _datos_excel(db, actor, tabla, finca_id, lote_id, confirmadas)
    contenido = libro_excel(tabla, columnas, _filtrar(filas, columnas, fecha_desde, fecha_hasta, buscar, tabla, producto_id))
    return Response(contenido, media_type=TIPO_EXCEL, headers={
        "Content-Disposition": f'attachment; filename="kardex-{tabla}.xlsx"',
        "Cache-Control": "private, no-store",
    })


@router.get("/resumen")
def resumen(fecha_desde: date | None = None, fecha_hasta: date | None = None,
            finca_id: int | None = Query(None, gt=0), db: Session = Depends(get_db), _actor=Depends(operador)):
    return _resumen(db, fecha_desde, fecha_hasta, finca_id)


def _resumen(db, fecha_desde, fecha_hasta, finca_id):
    hasta = fecha_hasta or hoy_bolivia()
    desde = fecha_desde or hasta - timedelta(days=29)
    _periodo(desde, hasta)
    fincas = _fincas(db)
    if finca_id is not None and finca_id not in fincas:
        raise HTTPException(404, "Finca no encontrada.")
    cosechas = [c for c in CosechaRepositoryImpl(db).list_all()
                if not c.borrador and (not finca_id or c.finca_id == finca_id)]
    existencias = resumen_por_producto(cosechas, MovimientoRepositoryImpl(db).list_all(finca_id), desde, hasta)
    unico = existencias[0] if len(existencias) == 1 and existencias[0]["unidad"] == "kg" else {}
    return {
        "desde": desde, "hasta": hasta, "existencias": existencias,
        "existencia_kg": unico.get("saldo", 0),
    }
