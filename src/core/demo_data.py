"""Datos de ejemplo para que el sistema se vea funcionando desde el primer arranque.

Solo se crean una vez: si ya existe el usuario "julio" o ya hay fincas, no se
toca nada. Asi el administrador puede borrar o cambiar los datos sin que
vuelvan a aparecer solos.
"""

from datetime import date, timedelta

from src.core.database import SessionLocal
from src.modules.auth.infrastructure.external_adapters import PasswordHasher
from src.modules.auth.infrastructure.models_db import UsuarioDB
from src.modules.inventory.infrastructure.models_db import FincaDB, LoteDB, ParcelaDB
from src.modules.kardex.infrastructure.models_db import CosechaDB, MovimientoDB
from src.modules.supliers.infrastructure.models_db import CosecheroDB

DEMO_USERNAME = "julio"
DEMO_PASSWORD = "julio123"


def seed_demo_data() -> None:
    db = SessionLocal()
    try:
        ya_existe = (
            db.query(UsuarioDB).filter(UsuarioDB.username == DEMO_USERNAME).first()
        )
        if ya_existe or db.query(FincaDB).count() > 0:
            return

        hoy = date.today()

        # ---------------------------------------------------------- productor
        julio = UsuarioDB(
            username=DEMO_USERNAME,
            password_hash=PasswordHasher.hash(DEMO_PASSWORD),
            nombre_completo="Julio Mamani",
            rol="cliente",
            activo=True,
        )
        db.add(julio)
        db.flush()

        # ---------------------------------------------------------- fincas
        finca1 = FincaDB(
            numero=1,
            nombre="Finca El Paraíso",
            ubicacion="Montero, Santa Cruz",
            usuario_id=julio.id,
        )
        finca2 = FincaDB(
            numero=2,
            nombre="Finca La Esperanza",
            ubicacion="Warnes, Santa Cruz",
            usuario_id=julio.id,
        )
        finca3 = FincaDB(
            numero=3,
            nombre="Finca San José",
            ubicacion="Portachuelo, Santa Cruz",
            usuario_id=None,
        )
        db.add_all([finca1, finca2, finca3])
        db.flush()

        p1 = ParcelaDB(finca_id=finca1.id, numero=1, superficie_ha=6.50)
        p2 = ParcelaDB(finca_id=finca1.id, numero=2, superficie_ha=6.00)
        p3 = ParcelaDB(finca_id=finca2.id, numero=1, superficie_ha=4.00)
        p4 = ParcelaDB(finca_id=finca2.id, numero=2, superficie_ha=4.00)
        p5 = ParcelaDB(finca_id=finca3.id, numero=1, superficie_ha=5.00)
        db.add_all([p1, p2, p3, p4, p5])
        db.flush()

        # ---------------------------------------------------------- cosecheros
        c1 = CosecheroDB(nombre="Juan Mamani", ci="7458123", telefono="71234567")
        c2 = CosecheroDB(nombre="María Flores", ci="8123456", telefono="72345678")
        c3 = CosecheroDB(nombre="Pedro Rojas", ci="6987451", telefono="73456789")
        db.add_all([c1, c2, c3])
        db.flush()

        # ---------------------------------------------------------- lotes
        lote1 = LoteDB(
            codigo="LOTE-2026-001",
            finca_id=finca1.id,
            fecha_ingreso=hoy - timedelta(days=34),
            detalle="Hoja fresca tipo exportación",
        )
        lote2 = LoteDB(
            codigo="LOTE-2026-002",
            finca_id=finca2.id,
            fecha_ingreso=hoy - timedelta(days=20),
            detalle="Hoja fresca segunda",
        )
        lote3 = LoteDB(
            codigo="LOTE-2026-003",
            finca_id=finca3.id,
            fecha_ingreso=hoy - timedelta(days=8),
            detalle="Hoja fresca",
        )
        db.add_all([lote1, lote2, lote3])
        db.flush()

        # ---------------------------------------------------------- cosechas
        cosechas = [
            (2, c1, finca1, p1, 520.500, 1821.75),
            (5, c2, finca1, p2, 480.000, 1680.00),
            (9, c3, finca2, p3, 610.250, 2135.88),
            (12, c1, finca2, p4, 395.750, 1385.13),
            (16, c2, finca1, p1, 540.000, 1890.00),
            (21, c3, finca2, p3, 470.500, 1646.75),
            (27, c1, finca1, p2, 505.250, 1768.38),
            (33, c2, finca3, p5, 300.000, 1050.00),
        ]
        for dias, cosechero, finca, parcela, kg, monto in cosechas:
            db.add(
                CosechaDB(
                    fecha=hoy - timedelta(days=dias),
                    cosechero_id=cosechero.id,
                    finca_id=finca.id,
                    parcela_id=parcela.id,
                    tipo_cosecha="HOJA FRESCA",
                    kg=kg,
                    monto_bs=monto,
                    observacion="Registro de ejemplo",
                )
            )

        # ---------------------------------------------------------- kardex
        movimientos = [
            (32, "Ingreso inicial de producto", "ING-001", lote1, finca1, 1200.000, 0.000),
            (26, "Entrega a centro de acopio", "SAL-001", lote1, finca1, 0.000, 450.000),
            (20, "Ingreso de cosecha", "ING-002", lote2, finca2, 900.000, 0.000),
            (14, "Entrega a centro de acopio", "SAL-002", lote2, finca2, 0.000, 700.000),
            (8, "Ingreso de cosecha", "ING-003", lote3, finca3, 1100.000, 0.000),
            (3, "Entrega a centro de acopio", "SAL-003", lote3, finca3, 0.000, 800.000),
        ]
        saldo = 0.0
        for dias, detalle, doc, lote, finca, entrada, salida in movimientos:
            saldo = saldo + entrada - salida
            db.add(
                MovimientoDB(
                    fecha=hoy - timedelta(days=dias),
                    detalle=detalle,
                    doc=doc,
                    lote_id=lote.id,
                    finca_id=finca.id,
                    entrada_kg=entrada,
                    salida_kg=salida,
                    saldo_kg=round(saldo, 3),
                    observacion="Registro de ejemplo",
                )
            )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
