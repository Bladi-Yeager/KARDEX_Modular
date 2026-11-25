"""Cortes de dirección con dos lotes y una base SQLite en memoria."""
import unittest
from datetime import date
from io import BytesIO
from unittest.mock import patch

from fastapi import HTTPException
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

def lote_vendido(db, etiqueta, fecha, producto, compra, venta, gasto):
    from src.modules.inventory.infrastructure.models_db import LoteDB
    from src.modules.kardex.infrastructure.models_db import CosechaDB, MovimientoDB
    from src.modules.reportes.finanzas import RegistroFinancieroDB

    cosecha = CosechaDB(fecha=fecha, finca_id=1, cosechero_id=1, kg=100, cantidad=100,
                        recibida=100, rechazada=0, monto_bs=compra, producto_id=producto.id)
    db.add(cosecha)
    db.flush()
    lote = LoteDB(codigo=etiqueta, fecha_ingreso=fecha, cosecha_id=cosecha.id,
                  finca_id=1, producto_id=producto.id)
    db.add(lote)
    db.flush()
    for tipo, entrada, salida in [("recepcion", 100, 0), ("movimiento", 0, 40)]:
        db.add(MovimientoDB(fecha=fecha, detalle=etiqueta, lote_id=lote.id, tipo=tipo,
                            cantidad_entrada=entrada, cantidad_salida=salida))
    for tipo, monto in [("venta", venta), ("costo", gasto)]:
        db.add(RegistroFinancieroDB(fecha=fecha, tipo=tipo, concepto=etiqueta, lote_id=lote.id,
                                    monto_bs=monto, registrado_por=1))


class DireccionMensualTest(unittest.TestCase):
    def setUp(self):
        from src.core.database import Base
        from src.modules.auth.infrastructure.models_db import UsuarioDB
        from src.modules.inventory.infrastructure.models_db import FincaDB, ProductoDB
        from src.modules.supliers.infrastructure.models_db import CosecheroDB
        from src.modules.reportes import direccion

        self.direccion = direccion
        self.hoy = date(2026, 3, 30)
        self.ayer = date(2026, 3, 29)
        reloj = patch.object(direccion, "hoy_bolivia", return_value=self.hoy)
        reloj.start()
        self.addCleanup(reloj.stop)
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        self.db = Session(engine)
        self.addCleanup(self.db.close)
        self.db.add_all([FincaDB(numero=1), CosecheroDB(nombre="Prueba"),
                         UsuarioDB(username="prueba", nombre_completo="Prueba", rol="admin", password_hash="inactivo")])
        self.producto = ProductoDB(nombre="Hoja de té", unidad="kg")
        self.db.add(self.producto)
        self.db.flush()
        for etiqueta, fecha, venta, gasto in [
            ("F", date(2026, 2, 28), 130, 10),
            ("A", self.hoy, 160, 20), ("B", self.hoy, 110, 10),
            ("C", self.ayer, 70, 10)
        ]:
            lote_vendido(self.db, etiqueta, fecha, self.producto, 200, venta, gasto)
        self.db.commit()

    def test_mes_dia_rango_excel(self):
        direccion = self.direccion
        mensual = direccion.mensual(db=self.db)
        self.assertEqual((mensual["anterior"]["desde"], mensual["anterior"]["hasta"]),
                         (date(2026, 2, 1), date(2026, 2, 28)))
        self.assertEqual((mensual["actual"]["resultado"], mensual["anterior"]["resultado"]), (60, 40))
        diario = direccion.resumen(1, self.hoy, self.hoy, self.db)
        self.assertEqual((diario["actual"]["ventas"], diario["actual"]["costo"],
                          diario["actual"]["gastos"], diario["actual"]["resultado"]), (270, 160, 30, 80))
        self.assertEqual((diario["recepciones"], diario["despachos"]), (2, 2))
        ayer = direccion.resumen(1, self.ayer, self.ayer, self.db)
        self.assertEqual(ayer["actual"]["resultado"], -20)
        for dias in [7, 30, 90]:
            r = direccion.resumen(dias, db=self.db)
            self.assertEqual((r["actual"]["hasta"]-r["actual"]["desde"]).days, dias-1)
        excel = direccion.excel_periodo(self.ayer, self.hoy, self.db)
        filas = list(load_workbook(BytesIO(excel.body)).active.values)
        self.assertEqual({f[2] for f in filas[1:-1]}, {"A", "B", "C"})
        self.assertEqual(filas[-1][7], 60)

    def test_pendiente_vacio_y_fechas(self):
        direccion = self.direccion
        lote_vendido(self.db, "Sin compra", self.hoy, self.producto, 0, 150, 10)
        self.db.commit()
        self.assertIsNone(direccion.mensual(db=self.db)["actual"]["resultado"])
        self.assertIsNone(direccion.resumen(1, db=self.db)["actual"]["resultado"])
        vacio = direccion.resumen(1, date(2026,3,2), date(2026,3,2), self.db)
        self.assertFalse(vacio["actual"]["actividad"])
        with self.assertRaises(HTTPException):
            direccion.excel_periodo(self.hoy, self.ayer, self.db)
        self.assertEqual(direccion.rangos_mes(date(2026,1,5))[2:], (date(2025,12,1),date(2025,12,5)))
        self.assertEqual(direccion.rangos_mes(date(2024,3,30))[-1], date(2024,2,29))

    def test_seleccion_calendario(self):
        mensual = self.direccion.mensual
        for anio, mes, fin, previo in [
            (2026, 2, date(2026, 2, 28), date(2026, 1, 31)),
            (2026, 1, date(2026, 1, 31), date(2025, 12, 31)),
            (2024, 2, date(2024, 2, 29), date(2024, 1, 31)),
        ]:
            with self.subTest(anio=anio, mes=mes):
                datos = mensual(db=self.db, anio=anio, mes=mes)
                self.assertEqual((datos["hasta"], datos["anterior"]["hasta"]), (fin, previo))
        futuro = mensual(db=self.db, anio=2027, mes=1)
        self.assertTrue(futuro["futuro"])
        self.assertIsNone(futuro["actual"])
        with self.assertRaises(HTTPException):
            mensual(db=self.db, anio=2026, mes=13)
