import os
import secrets

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        ""
    )
    # Clave para firmar los tokens de sesion. Cambiala en produccion (.env).
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    # Cuanto dura la sesion del usuario (minutos). 480 = 8 horas.
    TOKEN_EXPIRE_MINUTES: int = int(os.getenv("TOKEN_EXPIRE_MINUTES", "480"))
    DEMO_DATA: bool = False

    @field_validator("SECRET_KEY", mode="after")
    @classmethod
    def clave_sesion(cls, valor: str) -> str:
        valor = valor.strip()
        if len(valor) < 32 or valor.lower().startswith(("cambia-", "tu_clave", "pon_aqui")):
            # Genera una clave local por proceso para instalaciones sin una clave propia.
            return secrets.token_urlsafe(48)
        return valor


settings = Settings()
