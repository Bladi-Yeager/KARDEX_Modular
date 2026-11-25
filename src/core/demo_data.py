"""Ejemplo de acopio del Trópico para instalaciones vacías con DEMO_DATA=true."""

from datetime import timedelta

from src.core.database import SessionLocal
from src.core.fechas import hoy_bolivia
from src.modules.auth.infrastructure.external_adapters import PasswordHasher
from src.modules.auth.infrastructure.models_db import UsuarioDB
from src.modules.inventory.infrastructure.models_db import FincaDB, LoteDB, ProductoDB
from src.modules.kardex.infrastructure.models_db import CosechaDB, MovimientoDB
from src.modules.supliers.infrastructure.models_db import CosecheroDB

DEMO_USERNAME = "julio"
DEMO_PASSWORD = "julio123"


def seed_demo_data() -> None:
    with SessionLocal.begin() as db:
        if db.query(UsuarioDB.id).filter_by(username=DEMO_USERNAME).first() or db.query(FincaDB.id).first():
            return
        hoy = hoy_bolivia()
        cliente = UsuarioDB(username=DEMO_USERNAME, password_hash=PasswordHasher.hash(DEMO_PASSWORD),
                            nombre_completo="Productor de demostración", rol="cliente", activo=True)
        cosechero = CosecheroDB(nombre="Cosechero de demostración")
        db.add_all([cliente, cosechero])
        db.flush()
        catalogo = {(p.nombre, p.unidad): p for p in db.query(ProductoDB).all()}
        ejemplos = (
            ("Piña", "unidad", "Ivirgarzama", "PIN-001", 100, 8, 3, "merma", 0),
            ("Banano", "caja", "Chimoré", "BAN-001", 20, 0, 8, "movimiento", 1),
            ("Pitahaya", "kg", "Villa Tunari", "PIT-001", 40, 0, 15, "movimiento", 2),
        )
        for index, (nombre, unidad, localidad, codigo, llegada, rechazo, salida, tipo, dias) in enumerate(ejemplos, 1):
            producto = catalogo[nombre, unidad]
            fecha = hoy - timedelta(days=dias)
            finca = FincaDB(numero=index, nombre=f"Chaco demostración {index}",
                            ubicacion=localidad, usuario_id=cliente.id)
            db.add(finca)
            db.flush()
            aceptada = llegada - rechazo
            cosecha = CosechaDB(
                fecha=fecha, finca_id=finca.id, cosechero_id=cosechero.id,
                tipo_cosecha=nombre, producto_id=producto.id, cantidad=aceptada,
                kg=aceptada if unidad == "kg" else 0, monto_bs=0, borrador=False,
                recibida=llegada, rechazada=rechazo,
                motivo_rechazo="Daño al recibir" if rechazo else None,
            )
            db.add(cosecha)
            db.flush()
            lote = LoteDB(codigo=codigo, finca_id=finca.id, cosecha_id=cosecha.id,
                          producto_id=producto.id, fecha_ingreso=fecha, detalle=nombre)
            db.add(lote)
            db.flush()
            db.add(MovimientoDB(
                fecha=fecha, detalle="Recepción de demostración", lote_id=lote.id, finca_id=finca.id,
                cantidad_entrada=aceptada, cantidad_salida=0, tipo="recepcion",
                entrada_kg=aceptada if unidad == "kg" else 0, saldo_kg=aceptada if unidad == "kg" else 0,
            ))
            db.add(MovimientoDB(
                fecha=hoy, detalle="Merma de demostración" if tipo == "merma" else "Despacho de demostración",
                observacion="Daño en almacén" if tipo == "merma" else None,
                lote_id=lote.id, finca_id=finca.id, cantidad_entrada=0, cantidad_salida=salida, tipo=tipo,
                salida_kg=salida if unidad == "kg" else 0, saldo_kg=aceptada - salida if unidad == "kg" else 0,
            ))
