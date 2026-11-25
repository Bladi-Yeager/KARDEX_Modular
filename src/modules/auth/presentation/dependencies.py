from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

import jwt

from src.core.database import get_db
from src.modules.auth.infrastructure.repository_impl import UsuarioRepositoryImpl
from src.modules.auth.infrastructure.models_db import UsuarioDB
from src.modules.auth.infrastructure.tokens import decode_token
from src.modules.auth.domain.models import ROLES_VALIDOS, rol_efectivo

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Devuelve el usuario dueno del token. Si no hay token valido, corta con 401."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de acceso. Inicia sesion.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
        usuario_id = int(payload.get("sub", 0))
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesion vencio. Vuelve a iniciar sesion.",
        )
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido.",
        )

    usuario = UsuarioRepositoryImpl(db).get_by_id(usuario_id)
    if usuario is None or not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El usuario no existe o esta inactivo.",
        )
    usuario.rol = rol_efectivo(usuario.rol)
    if usuario.rol not in ROLES_VALIDOS:
        raise HTTPException(status_code=403, detail="El perfil requiere actualización.")
    return usuario


def require_roles(*roles: str):
    """Fabrica de dependencias: solo deja pasar a los roles indicados."""

    def checker(usuario=Depends(get_current_user)):
        if usuario.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para esta accion.",
            )
        return usuario

    return checker


def validar_productor(db: Session, usuario_id: int | None):
    if usuario_id is not None:
        usuario = db.get(UsuarioDB, usuario_id)
        if usuario is None or not usuario.activo or rol_efectivo(usuario.rol) != "cliente":
            raise HTTPException(422, "Selecciona una cuenta de productor activa.")
