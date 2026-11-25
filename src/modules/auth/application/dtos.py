from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ClienteRegister(BaseModel):
    """Registro libre: solo crea clientes/productores. El rol no se elige."""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=72)
    nombre_completo: str = Field(min_length=3, max_length=100)

    @field_validator("username", "nombre_completo", mode="before")
    @classmethod
    def limpiar(cls, valor):
        return valor.strip() if isinstance(valor, str) else valor

    @field_validator("password")
    @classmethod
    def limite_bcrypt(cls, valor: str) -> str:
        if len(valor.encode("utf-8")) > 72:
            raise ValueError("La contraseña supera el límite admitido de 72 bytes.")
        return valor


class StaffRegister(BaseModel):
    """Registro con invitacion: el rol lo define la invitacion, no el formulario."""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=72)
    nombre_completo: str = Field(min_length=3, max_length=100)
    codigo_invitacion: str = Field(min_length=4, max_length=40)


class AdminBootstrap(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=72)
    nombre_completo: str = Field(min_length=3, max_length=100)


class UsuarioCreateAdmin(ClienteRegister):
    password: str = Field(min_length=12, max_length=72)
    rol: str = "cliente"


class UsuarioLogin(BaseModel):
    username: str
    password: str


class InvitacionCreate(BaseModel):
    rol: str = "trabajador"
    dias_vigencia: int = Field(default=7, ge=1, le=90)


class InvitacionOut(BaseModel):
    id: int
    codigo: str
    rol: str
    expira_en: datetime
    usado: bool
    activo: bool

    class Config:
        from_attributes = True


class UsuarioOut(BaseModel):
    id: int
    username: str
    nombre_completo: str
    rol: str
    activo: bool

    class Config:
        from_attributes = True


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut
