from sqlalchemy import Boolean, Column, Integer, String, DECIMAL, Date, ForeignKey, false
from src.core.database import Base


class CosechaDB(Base):
    __tablename__ = "cosechas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    fecha = Column(Date, nullable=False)
    cosechero_id = Column(Integer, ForeignKey("cosecheros.id"), nullable=False)
    finca_id = Column(Integer, ForeignKey("fincas.id"), nullable=False)
    parcela_id = Column(Integer, ForeignKey("parcelas.id"), nullable=True)
    tipo_cosecha = Column(String(50), nullable=False, default="HOJA FRESCA")
    kg = Column(DECIMAL(12, 3), nullable=False)
    monto_bs = Column(DECIMAL(12, 2), nullable=False, default=0)
    observacion = Column(String(200), nullable=True)
    borrador = Column(Boolean, nullable=False, server_default=false())
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=True, index=True)
    cantidad = Column(DECIMAL(12, 3), nullable=True)
    recibida = Column(DECIMAL(12, 3), nullable=True)
    rechazada = Column(DECIMAL(12, 3), nullable=True)
    motivo_rechazo = Column(String(200), nullable=True)
    cantidad_secundaria = Column(DECIMAL(12, 3), nullable=True)
    unidad_secundaria = Column(String(10), nullable=True)
    documento_recepcion = Column(String(30), nullable=True)


class ControlKardexDB(Base):
    __tablename__ = "kardex_control"

    id = Column(Integer, primary_key=True, autoincrement=False)
    revision = Column(Integer, nullable=False, default=0)


class MovimientoDB(Base):
    __tablename__ = "kardex_movimientos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    fecha = Column(Date, nullable=False)
    detalle = Column(String(150), nullable=False)
    doc = Column(String(30), nullable=True)
    lote_id = Column(Integer, ForeignKey("lotes.id"), nullable=True)
    finca_id = Column(Integer, ForeignKey("fincas.id"), nullable=True)
    entrada_kg = Column(DECIMAL(12, 3), nullable=False, default=0)
    salida_kg = Column(DECIMAL(12, 3), nullable=False, default=0)
    saldo_kg = Column(DECIMAL(12, 3), nullable=False, default=0)
    observacion = Column(String(200), nullable=True)
    anula_movimiento_id = Column(Integer, ForeignKey("kardex_movimientos.id"), unique=True, nullable=True)
    registrado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    cantidad_entrada = Column(DECIMAL(12, 3), nullable=True)
    cantidad_salida = Column(DECIMAL(12, 3), nullable=True)
    tipo = Column(String(12), nullable=True)
