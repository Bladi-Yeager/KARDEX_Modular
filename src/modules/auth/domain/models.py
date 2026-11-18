from dataclasses import dataclass
from datetime import datetime
from typing import Optional


ROLES_VALIDOS = ("admin", "encargado", "trabajador", "cliente")


@dataclass
class Usuario:
    username: str
    password_hash: str
    nombre_completo: str
    rol: str = "cliente"
    id: Optional[int] = None
    activo: bool = True


@dataclass
class Invitacion:
    codigo: str
    rol: str
    expira_en: datetime
    creado_por: Optional[int] = None
    usado_por: Optional[int] = None
    usado_en: Optional[datetime] = None
    activo: bool = True
    id: Optional[int] = None

    @property
    def usado(self) -> bool:
        return self.usado_por is not None

    def esta_vigente(self, ahora: Optional[datetime] = None) -> bool:
        ahora = ahora or datetime.now()
        return self.activo and self.usado_por is None and self.expira_en > ahora
