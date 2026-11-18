from datetime import datetime, timedelta, timezone

import jwt

from src.core.config import settings


def create_access_token(usuario) -> str:
    """Genera el token de sesion (JWT) del usuario."""
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario.id),
        "username": usuario.username,
        "rol": usuario.rol,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=settings.TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """Valida la firma y el vencimiento del token."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
