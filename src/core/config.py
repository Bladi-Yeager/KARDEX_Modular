import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:tu_password_root@localhost:33061/db_kardex"
    )
    # Clave para firmar los tokens de sesion. Cambiala en produccion (.env).
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "cambia-esta-clave-por-una-larga-y-secreta-kardex-2026"
    )
    ALGORITHM: str = "HS256"
    # Cuanto dura la sesion del usuario (minutos). 480 = 8 horas.
    TOKEN_EXPIRE_MINUTES: int = int(os.getenv("TOKEN_EXPIRE_MINUTES", "480"))


settings = Settings()
