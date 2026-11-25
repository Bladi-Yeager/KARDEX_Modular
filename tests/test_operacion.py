"""Regresiones del Kardex, permisos y Excel con una base SQLite desechable."""

import atexit
import asyncio
import os
import tempfile
import unittest
from datetime import timedelta
from io import BytesIO
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from openpyxl import load_workbook

carpeta = tempfile.TemporaryDirectory(prefix="kardex-tests-")
os.environ["DATABASE_URL"] = os.environ.get("KARDEX_TEST_MYSQL_URL") or (
    "sqlite:///" + (Path(carpeta.name) / "app.sqlite").as_posix()
)
os.environ["DEMO_DATA"] = "false"

from src.core.database import SessionLocal, engine
from src.core.fechas import hoy_bolivia
from src.main import app
from src.modules.auth.application.dtos import ClienteRegister
from src.modules.auth.application.services import AuthService
from src.modules.auth.infrastructure.repository_impl import UsuarioRepositoryImpl
from src.modules.kardex.infrastructure.models_db import MovimientoDB

atexit.register(lambda: (engine.dispose(), carpeta.cleanup()))


class OperacionTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.api = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
        self.addAsyncCleanup(self.api.aclose)

    async def test_flujo_permisos_saldos_y_excel(self):
        password = "prueba-segura-123"
        fecha = hoy_bolivia()
        data_usuario = lambda nombre: {"username": nombre, "password": password, "nombre_completo": nombre}
        with SessionLocal() as db:
            auth = AuthService(UsuarioRepositoryImpl(db))
            for nombre, rol in [("jefe-pruebas", "jefe"), ("soporte-pruebas", "soporte"), ("operador","admin")]:
                auth.provisionar(ClienteRegister(**data_usuario(nombre)), rol)

        async def login(nombre):
            respuesta = await self.api.post("/auth/login", json={"username": nombre, "password": password})
            self.assertEqual(respuesta.status_code, 200, respuesta.text)
            return {"Authorization": "Bearer " + respuesta.json()["access_token"]}

        async def enviar(path, actor, data, codigo=201):
            r = await self.api.post(path, headers=actor, json=data)
            self.assertEqual(r.status_code, codigo, r.text)
            return r.json()

        async def leer(path, actor, codigo=200):
            r = await self.api.get(path, headers=actor)
            self.assertEqual(r.status_code, codigo, r.text)
            return r

        jefe = await login("jefe-pruebas")
        soporte = await login("soporte-pruebas")
        await enviar("/auth/usuarios", jefe, dict(data_usuario("otro-operador"), rol="admin"), 403)
        admin = await login("operador")
        productor_a = await enviar("/auth/usuarios", admin, dict(data_usuario("productor-a"), rol="cliente"))
        productor_b = await enviar("/auth/register", {}, data_usuario("productor-b"), 200)
        self.assertFalse(productor_b["activo"])
        await enviar("/auth/login", {}, {"username": "productor-b", "password": password}, 403)
        self.assertEqual([u["id"] for u in (await leer("/auth/solicitudes", admin)).json()], [productor_b["id"]])
        solicitud = f"/auth/solicitudes/{productor_b['id']}/aprobar"
        chaco_b = await enviar("/inventario/fincas", admin, {"numero": 2, "nombre": "Finca 2"}, 200)
        await enviar(solicitud, jefe, {"finca_id": chaco_b["id"]}, 403)
        await enviar(solicitud, admin, {"finca_id": chaco_b["id"]}, 200)
        await enviar(solicitud, admin, {"finca_id": chaco_b["id"]}, 409)
        await leer("/finanzas/lotes", admin, 403)
        await leer("/reportes/excel/resultado-lotes", admin, 403)
        self.assertNotIn("finanzas", (await leer("/reportes/resumen", admin)).json())
        pa, pb = await login("productor-a"), await login("productor-b")
        self.assertEqual([c["id"] for c in (await leer("/portal/api/mis-fincas", pb)).json()], [chaco_b["id"]])
        from src.modules.auth.infrastructure.models_db import UsuarioDB
        with SessionLocal() as db:
            db.get(UsuarioDB, productor_a["id"]).rol = "trabajador"
            db.commit()
        pa = await login("productor-a")
        self.assertEqual((await leer("/auth/me", pa)).json()["rol"], "cliente")
        for actor in (pa, pb, soporte):
            await leer("/kardex/movimientos", actor, 403)
        await leer("/reportes/diagnostico", soporte)
        await leer("/reportes/diagnostico", admin, 403)
        await leer("/reportes/excel/finanzas", pa, 403)
        await enviar("/inventario/fincas", jefe, {"numero": 1}, 403)
        await enviar("/auth/usuarios", admin, dict(data_usuario("otro-admin"), rol="admin"), 403)

        fincas = []
        for num, productor in enumerate((productor_a, productor_b), 1):
            finca = chaco_b if num == 2 else await enviar("/inventario/fincas", admin, {"numero": num, "nombre": f"Finca {num}"}, 200)
            await enviar("/portal/api/admin/asignar-finca", admin, {"finca_id": finca["id"], "usuario_id": productor["id"]}, 200)
            fincas.append(finca["id"])
        cosechero = await enviar("/cosecheros", admin, {"nombre": "Cosechero de prueba"}, 200)
        catalogo = {(p["nombre"], p["unidad"]): p["id"] for p in (await leer("/inventario/productos", admin)).json()}
        pitahaya = catalogo["Pitahaya", "kg"]
        pina = catalogo["Piña", "unidad"]
        banano = catalogo["Banano", "caja"]

        async def preparar(finca, cantidad, producto=pitahaya, codigo=201):
            return await enviar("/kardex/cosechas", admin, {
                "fecha": fecha.isoformat(), "finca_id": finca, "cosechero_id": cosechero["id"],
                "producto_id": producto, "cantidad": cantidad,
            }, codigo)

        await preparar(fincas[1], 13)
        self.assertEqual((await leer("/portal/api/mis-cosechas", pb)).json(), [])
        primera = await preparar(fincas[0], 100)
        segunda = await preparar(fincas[1], 25)
        for cosecha, codigo in ((primera, "PR-100"), (segunda, "PR-025")):
            await enviar(f"/kardex/cosechas/{cosecha['id']}/recepcion", admin, {
                "codigo": codigo, "fecha": fecha.isoformat(), "monto_bs": 50 if codigo == "PR-025" else 0,
            })
        await enviar(f"/kardex/cosechas/{segunda['id']}/recepcion", admin, {"codigo": "REP", "fecha": fecha.isoformat()}, 409)
        resumen_b = (await leer("/portal/api/resumen", pb)).json()
        self.assertEqual((resumen_b["entradas_kg"], resumen_b["saldo_kg"]), (25, 25))
        self.assertEqual((await leer("/kardex/movimientos", admin)).json()[-1]["saldo_kg"], 125)
        lote_b = (await leer("/portal/api/mis-lotes", pb)).json()[0]["id"]
        salida = {"fecha": fecha.isoformat(), "detalle": "Despacho de prueba", "lote_id": lote_b, "salida_kg": 10}
        await enviar("/kardex/movimientos", admin, dict(salida, salida_kg=26), 409)
        await enviar("/kardex/movimientos", admin, dict(salida, finca_id=fincas[0]), 422)
        mov = await enviar("/kardex/movimientos", admin, dict(salida, saldo_kg=99999))
        self.assertEqual(mov["saldo_kg"], 115)
        self.assertEqual((await leer("/portal/api/resumen", pb)).json()["saldo_kg"], 15)
        await enviar(f"/kardex/movimientos/{mov['id']}/anular", admin, {"motivo": "Se canceló el despacho"})
        await enviar(f"/kardex/movimientos/{mov['id']}/anular", admin, {"motivo": "Operación repetida"}, 409)
        self.assertEqual((await leer("/portal/api/resumen", pb)).json()["saldo_kg"], 25)

        xlsx = await leer("/reportes/excel/kardex?buscar=recepcion", pb)
        hoja = load_workbook(BytesIO(xlsx.content), data_only=False).active
        contenido = list(hoja.values)
        self.assertEqual(len(contenido), 2)
        self.assertIn("PR-025", contenido[1])
        self.assertNotIn("PR-100", contenido[1])
        self.assertIn(25, contenido[1])
        historial = await leer(f"/kardex/movimientos?lote_id={lote_b}", admin)
        self.assertEqual([m["saldo_kg"] for m in historial.json()], [25, 15, 25])

        # Dos despachos simultáneos no pueden comprometer la misma existencia.
        concurrentes = await asyncio.gather(*(
            self.api.post("/kardex/movimientos", headers=admin, json=dict(salida, salida_kg=16))
            for _ in range(2)
        ))
        self.assertEqual(sorted(r.status_code for r in concurrentes), [201, 409])
        self.assertEqual((await leer("/portal/api/resumen", pb)).json()["saldo_kg"], 9)

        for tipo, monto in (("venta", 150), ("costo", 60)):
            data = {"fecha": fecha.isoformat(), "tipo": tipo, "concepto": "=Dato escrito", "lote_id": lote_b, "monto_bs": monto}
            await enviar("/finanzas", admin, data)
            await enviar("/finanzas", jefe, data, 403)
        for ruta in ("/reportes/resumen", "/inventario/productos", "/kardex/movimientos",
                     "/finanzas", "/auth/usuarios", "/reportes/excel/finanzas", "/reportes/excel/cuentas"):
            await leer(ruta, jefe, 403)
        xlsx = await leer("/reportes/excel/finanzas", admin)
        celda = load_workbook(BytesIO(xlsx.content), data_only=False).active["C2"]
        self.assertEqual(celda.value, "=Dato escrito")
        self.assertEqual(celda.data_type, "s")

        await leer("/direccion/resumen", admin, 403)
        informe = (await leer("/direccion/resumen", jefe)).json()
        self.assertEqual(next(l["resultado"] for l in informe["actual"]["lotes"] if l["codigo"]=="PR-025"), 58)
        lotes_fin = (await leer("/finanzas/lotes", jefe)).json()
        balance = next(lote for lote in lotes_fin if lote["codigo"] == "PR-025")
        self.assertEqual((balance["saldo"], balance["costo_salidas_bs"], balance["resultado_bs"]), (9, 32, 58))
        self.assertIsNone(next(lote for lote in lotes_fin if lote["codigo"] == "PR-100")["resultado_bs"])
        await leer("/finanzas/lotes", pa, 403)
        await enviar("/finanzas", admin, dict(data, tipo="compra"), 409)
        await enviar("/finanzas", admin, dict(data, tipo="venta", lote_id=None), 422)
        gasto = await enviar("/finanzas", admin, dict(data, monto_bs=100))
        async def margen():
            filas = (await leer("/finanzas/lotes", jefe)).json()
            return next(f["resultado_bs"] for f in filas if f["codigo"] == "PR-025")
        self.assertEqual(await margen(), -42)
        await enviar(f"/finanzas/{gasto['id']}/anular", admin, {"motivo": "Gasto duplicado"}, 200)
        self.assertEqual(await margen(), 58)
        libro = await leer("/reportes/excel/resultado-lotes", jefe)
        filas = list(load_workbook(BytesIO(libro.content)).active.values)
        self.assertIn(58, next(fila for fila in filas if "PR-025" in fila))
        # Un corte anterior al ingreso conserva el saldo real de ese período.
        corte = (fecha - timedelta(days=1)).isoformat()
        reporte = (await leer("/reportes/resumen?fecha_hasta=" + corte, admin)).json()
        self.assertEqual(reporte["existencia_kg"], 0)

        await preparar(fincas[0], "2.5", pina, 422)
        lotes = {}
        for producto, total, codigo in ((pina, 100, "PIN-001"), (banano, 20, "BAN-001")):
            c = await preparar(fincas[0], total, producto)
            recepcion = {"codigo": codigo, "fecha": fecha.isoformat(), "recibida": total}
            if producto == pina:
                await enviar(f"/kardex/cosechas/{c['id']}/recepcion", admin, dict(recepcion, rechazada=8), 422)
                recepcion.update(rechazada=8, motivo_rechazo="Daño en la entrega",
                                 cantidad_secundaria=110.5, unidad_secundaria="kg", monto_bs=184)
            r = await enviar(f"/kardex/cosechas/{c['id']}/recepcion", admin, recepcion)
            lotes[producto] = r["lote_id"]
            self.assertEqual(r["aceptada"], 92 if producto == pina else 20)

        await enviar("/kardex/movimientos", admin, {
            "fecha": fecha.isoformat(), "detalle": "Peso inválido como cajas", "lote_id": lotes[banano], "salida_kg": 1,
        }, 422)
        for producto, cantidad, tipo in ((pina, 3, "merma"), (banano, 8, "movimiento")):
            await enviar("/kardex/movimientos", admin, {
                "fecha": fecha.isoformat(), "detalle": "Salida de prueba", "lote_id": lotes[producto],
                "cantidad_salida": cantidad, "tipo": tipo, "observacion": "Daño en almacén" if tipo == "merma" else None,
            })
        await enviar("/kardex/movimientos", admin, {
            "fecha": fecha.isoformat(), "detalle": "Despacho mayor al lote", "lote_id": lotes[banano], "cantidad_salida": 13,
        }, 409)
        rechazo = await preparar(fincas[1], 5, banano)
        total = await enviar(f"/kardex/cosechas/{rechazo['id']}/recepcion", admin, {
            "fecha": fecha.isoformat(), "codigo": "BAN-RECH", "recibida": 5,
            "rechazada": 5, "motivo_rechazo": "Rechazo total de prueba",
        })
        self.assertEqual(total["aceptada"], 0)
        self.assertIsNone(total["movimiento"])

        reporte = await leer(f"/reportes/resumen?fecha_desde={fecha}&fecha_hasta={fecha}", admin)
        grupos = {p["producto_id"]: p for p in reporte.json()["existencias"]}
        self.assertEqual({p: (g["unidad"], float(g["saldo"])) for p, g in grupos.items()},
                         {pina: ("unidad", 89), banano: ("caja", 12), pitahaya: ("kg", 109)})
        self.assertEqual(float(grupos[pina]["recibida"]), 100)
        self.assertEqual(float(grupos[pina]["entrada"]), 92)
        self.assertEqual(float(grupos[pina]["rechazada"]), 8)
        self.assertEqual(float(grupos[pina]["merma"]), 3)
        vista_b = await leer("/portal/api/resumen", pb)
        self.assertNotIn(pina, {p["producto_id"] for p in vista_b.json()["existencias"]})
        comprobantes = await leer("/portal/api/mis-cosechas", pa)
        recibo = next(c for c in comprobantes.json() if c["producto_id"] == pina)
        self.assertEqual((recibo["codigo_lote"], recibo["recibida"], recibo["cantidad_secundaria"]), ("PIN-001", 100, 110.5))
        self.assertEqual(recibo["monto_bs"], 184)
        archivo = await leer(f"/reportes/excel/existencias?producto_id={pina}&fecha_desde={fecha}&fecha_hasta={fecha}", admin)
        filas = list(load_workbook(BytesIO(archivo.content)).active.values)
        self.assertEqual(len(filas), 2)
        self.assertEqual(filas[1][2:4], ("Piña", "unidad"))
        self.assertEqual(filas[1][-1], 89)

        with SessionLocal.begin() as db:
            db.add(MovimientoDB(finca_id=fincas[0], fecha=fecha, detalle="Ingreso histórico",
                                entrada_kg=7, saldo_kg=999))
        historia = await leer("/kardex/movimientos?producto_id=0", admin)
        self.assertEqual([(m["producto"], m["cantidad_saldo"]) for m in historia.json()], [("Histórico sin clasificar", 7)])
        modernas = await leer(f"/kardex/movimientos?producto_id={pina}", admin)
        self.assertEqual(modernas.json()[-1]["cantidad_saldo"], 89)


        parcela = await enviar("/inventario/parcelas", admin, {"numero": 17, "finca_id": fincas[0], "superficie_ha": 2}, 200)
        base = {"fecha": str(fecha), "parcela_id": parcela["id"], "detalle": "Registro de campo"}
        await enviar("/bitacora", jefe, dict(base, tipo="Incidencia"), 403)
        await leer("/bitacora", pa, 403)
        await enviar("/bitacora", admin, dict(base, tipo="Abono"), 422)
        await enviar("/bitacora", admin, dict(base, tipo="Abono", insumo="Compost", dosis=25, unidad_dosis="kg/ha"))
        await enviar("/bitacora", admin, dict(base, tipo="Incidencia", detalle="Lluvia intensa"))
        for dias, cantidad, area in ((0, 90, 1), (8, 100, 2)):
            dia = str(fecha - timedelta(days=dias))
            c = await enviar("/kardex/cosechas", admin, {"fecha": dia, "finca_id": fincas[0],
                "parcela_id": parcela["id"], "cosechero_id": cosechero["id"], "producto_id": pina, "cantidad": cantidad})
            await enviar(f"/kardex/cosechas/{c['id']}/recepcion", admin, {"fecha": dia, "codigo": f"CAMPO-{dias}"})
            anotacion = dict(base, tipo="Cosecha", fecha=dia, cosecha_id=c["id"], area_ha=area)
            await enviar("/bitacora", admin, dict(anotacion, area_ha=3), 422)
            await enviar("/bitacora", admin, anotacion)
            await enviar("/bitacora", admin, anotacion, 409)
        j = (await leer("/direccion/resumen?dias=7", jefe)).json()["campo"]
        r = j["rendimientos"][0]
        self.assertEqual((r["actual"], r["anterior"], r["cambio_pct"]), (90, 50, 80))
        self.assertEqual(len(j["actividades"]), 3)
        await leer("/reportes/excel/bitacora", admin)



if __name__ == "__main__":
    unittest.main()
