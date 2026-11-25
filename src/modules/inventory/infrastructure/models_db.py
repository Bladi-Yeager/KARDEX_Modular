from sqlalchemy import Column, Integer, String, Boolean, DECIMAL, Date, TIMESTAMP, ForeignKey, UniqueConstraint, func
from src.core.database import Base


class FincaDB(Base):
    __tablename__ = "fincas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    numero = Column(Integer, unique=True, nullable=False)
    nombre = Column(String(100), nullable=True)
    ubicacion = Column(String(150), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    activo = Column(Boolean, nullable=False, default=True)


class ParcelaDB(Base):
    __tablename__ = "parcelas"
    __table_args__ = (UniqueConstraint("finca_id", "numero", name="uq_parcela"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    finca_id = Column(Integer, ForeignKey("fincas.id"), nullable=False)
    numero = Column(Integer, nullable=False)
    superficie_ha = Column(DECIMAL(10, 2), nullable=True)
    activo = Column(Boolean, nullable=False, default=True)


class ProductoDB(Base):
    __tablename__ = "productos"
    __table_args__ = (UniqueConstraint("nombre", "unidad", name="uq_producto_unidad"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(70), nullable=False)
    unidad = Column(String(10), nullable=False)


class LoteDB(Base):
    __tablename__ = "lotes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    codigo = Column(String(30), unique=True, nullable=False)
    finca_id = Column(Integer, ForeignKey("fincas.id"), nullable=True)
    cosecha_id = Column(Integer, ForeignKey("cosechas.id"), unique=True, nullable=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=True, index=True)
    fecha_ingreso = Column(Date, nullable=False)
    detalle = Column(String(150), nullable=True)
    creado_en = Column(TIMESTAMP, server_default=func.now())
