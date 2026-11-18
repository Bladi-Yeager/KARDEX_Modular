from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, DateTime, ForeignKey, func
from src.core.database import Base


class UsuarioDB(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nombre_completo = Column(String(100), nullable=False)
    rol = Column(String(32), nullable=False, default="cliente")
    activo = Column(Boolean, nullable=False, default=True)
    creado_en = Column(TIMESTAMP, server_default=func.now())


class InvitacionDB(Base):
    __tablename__ = "invitaciones"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    codigo = Column(String(40), unique=True, nullable=False, index=True)
    rol = Column(String(32), nullable=False)
    creado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    usado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    expira_en = Column(DateTime, nullable=False)
    usado_en = Column(DateTime, nullable=True)
    activo = Column(Boolean, nullable=False, default=True)
    creado_en = Column(TIMESTAMP, server_default=func.now())
