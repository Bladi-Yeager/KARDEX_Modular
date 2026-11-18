from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.modules.auth.application.dtos import (
    AdminBootstrap,
    ClienteRegister,
    InvitacionCreate,
    InvitacionOut,
    LoginOut,
    StaffRegister,
    UsuarioLogin,
    UsuarioOut,
)
from src.modules.auth.application.services import AuthService, InvitacionService
from src.modules.auth.domain.exceptions import (
    AdminYaExiste,
    CredencialesInvalidas,
    InvitacionInvalida,
    RolInvalido,
    UsuarioInactivo,
    UsuarioYaExiste,
)
from src.modules.auth.infrastructure.repository_impl import (
    InvitacionRepositoryImpl,
    UsuarioRepositoryImpl,
)
from src.modules.auth.presentation.dependencies import get_current_user, require_roles

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(UsuarioRepositoryImpl(db))


def get_invitacion_service(db: Session = Depends(get_db)) -> InvitacionService:
    return InvitacionService(InvitacionRepositoryImpl(db))


# --------------------------------------------------------------------- registro
@router.post("/register", response_model=UsuarioOut)
def register_cliente(data: ClienteRegister, service: AuthService = Depends(get_auth_service)):
    """Registro libre. Siempre crea un usuario con rol 'cliente' (productor)."""
    try:
        return service.register_cliente(data)
    except UsuarioYaExiste as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/register-staff", response_model=UsuarioOut)
def register_staff(
    data: StaffRegister,
    service: AuthService = Depends(get_auth_service),
    invitaciones: InvitacionService = Depends(get_invitacion_service),
):
    """Registro de encargado o trabajador: exige un codigo de invitacion vigente."""
    try:
        invitacion = invitaciones.obtener_vigente(data.codigo_invitacion)
        usuario = service.register_staff(data, invitacion)
        invitaciones.marcar_usada(invitacion, usuario.id)
        return usuario
    except InvitacionInvalida as e:
        raise HTTPException(status_code=400, detail=str(e))
    except UsuarioYaExiste as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bootstrap-admin", response_model=UsuarioOut)
def bootstrap_admin(data: AdminBootstrap, service: AuthService = Depends(get_auth_service)):
    """Crea el administrador principal una sola vez (instalacion nueva)."""
    try:
        return service.bootstrap_admin(data)
    except AdminYaExiste as e:
        raise HTTPException(status_code=400, detail=str(e))
    except UsuarioYaExiste as e:
        raise HTTPException(status_code=400, detail=str(e))


# --------------------------------------------------------------------- sesion
@router.post("/login", response_model=LoginOut)
def login(data: UsuarioLogin, service: AuthService = Depends(get_auth_service)):
    try:
        return service.login(data)
    except CredencialesInvalidas as e:
        raise HTTPException(status_code=401, detail=str(e))
    except UsuarioInactivo as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/me", response_model=UsuarioOut)
def me(usuario=Depends(get_current_user)):
    return usuario


# --------------------------------------------------------------------- admin
@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(
    service: AuthService = Depends(get_auth_service),
    _admin=Depends(require_roles("admin")),
):
    return service.list_all()


@router.post("/invitaciones", response_model=InvitacionOut)
def crear_invitacion(
    data: InvitacionCreate,
    service: InvitacionService = Depends(get_invitacion_service),
    admin=Depends(require_roles("admin")),
):
    try:
        return service.crear(data, creado_por=admin.id)
    except RolInvalido as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/invitaciones", response_model=list[InvitacionOut])
def listar_invitaciones(
    service: InvitacionService = Depends(get_invitacion_service),
    _admin=Depends(require_roles("admin")),
):
    return service.listar()
