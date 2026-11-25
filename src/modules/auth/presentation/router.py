from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.modules.auth.application.dtos import ClienteRegister, LoginOut, UsuarioCreateAdmin, UsuarioLogin, UsuarioOut
from src.modules.auth.application.services import AuthService
from src.modules.auth.domain.exceptions import CredencialesInvalidas, RolInvalido, UsuarioInactivo, UsuarioYaExiste
from src.modules.auth.domain.exceptions import SolicitudPendiente
from src.modules.inventory.infrastructure.models_db import FincaDB
from src.modules.auth.domain.models import rol_efectivo
from src.modules.auth.infrastructure.models_db import UsuarioDB
from src.modules.auth.infrastructure.repository_impl import UsuarioRepositoryImpl
from src.modules.auth.presentation.dependencies import get_current_user, require_roles

router = APIRouter(prefix="/auth", tags=["auth"])
gestiona_cuentas = require_roles("jefe", "admin")


class EstadoCuenta(BaseModel):
    activo: bool


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(UsuarioRepositoryImpl(db))


def rol_gestionado(rol: str) -> str:
    return "admin" if rol == "jefe" else "cliente"


@router.post("/register", response_model=UsuarioOut)
def register_cliente(data: ClienteRegister, service: AuthService = Depends(get_auth_service)):
    try:
        return service.register_cliente(data)
    except (UsuarioYaExiste, IntegrityError) as error:
        raise HTTPException(409, "El nombre de usuario ya existe.") from error


@router.post("/login", response_model=LoginOut)
def login(data: UsuarioLogin, service: AuthService = Depends(get_auth_service)):
    try:
        return service.login(data)
    except CredencialesInvalidas as error:
        raise HTTPException(401, str(error)) from error
    except SolicitudPendiente as error:
        raise HTTPException(403, "Tu solicitud sigue pendiente de aprobación por el administrador.") from error
    except UsuarioInactivo as error:
        raise HTTPException(403, "La cuenta está inactiva o su perfil requiere actualización.") from error


class Aprobacion(BaseModel):
    finca_id: int


@router.get("/solicitudes", response_model=list[UsuarioOut])
def solicitudes(db: Session = Depends(get_db), _actor=Depends(require_roles("admin"))):
    return db.query(UsuarioDB).filter_by(rol="pendiente").order_by(UsuarioDB.id).all()


@router.post("/solicitudes/{usuario_id}/aprobar", response_model=UsuarioOut)
def aprobar(usuario_id: int, data: Aprobacion, db: Session = Depends(get_db),
            _actor=Depends(require_roles("admin"))):
    usuario = db.get(UsuarioDB, usuario_id, with_for_update=True)
    if usuario is None or usuario.rol != "pendiente":
        raise HTTPException(409, "La solicitud ya no está pendiente.")
    finca = db.get(FincaDB, data.finca_id, with_for_update=True)
    if finca is None or not finca.activo or finca.usuario_id is not None:
        raise HTTPException(409, "Selecciona un chaco activo sin asignar.")
    finca.usuario_id = usuario.id
    usuario.rol = "cliente"
    usuario.activo = True
    db.commit()
    return usuario


@router.get("/me", response_model=UsuarioOut)
def me(usuario=Depends(get_current_user)):
    return usuario


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(service: AuthService = Depends(get_auth_service), actor=Depends(gestiona_cuentas)):
    usuarios = []
    for usuario in service.list_all():
        usuario.rol = rol_efectivo(usuario.rol)
        if usuario.rol == rol_gestionado(actor.rol):
            usuarios.append(usuario)
    return usuarios


@router.post("/usuarios", response_model=UsuarioOut, status_code=201)
def crear_usuario(data: UsuarioCreateAdmin, service: AuthService = Depends(get_auth_service), actor=Depends(gestiona_cuentas)):
    try:
        return service.crear_usuario(data, actor.rol)
    except RolInvalido as error:
        raise HTTPException(403, "No puedes crear cuentas con ese perfil.") from error
    except (UsuarioYaExiste, IntegrityError) as error:
        raise HTTPException(409, "El nombre de usuario ya existe.") from error


@router.patch("/usuarios/{usuario_id}/estado", response_model=UsuarioOut)
def cambiar_estado(usuario_id: int, data: EstadoCuenta, db: Session = Depends(get_db), actor=Depends(gestiona_cuentas)):
    row = db.get(UsuarioDB, usuario_id)
    if row is None or rol_efectivo(row.rol) != rol_gestionado(actor.rol):
        raise HTTPException(404, "Cuenta no encontrada.")
    row.activo = data.activo
    db.commit()
    usuario = UsuarioRepositoryImpl(db).get_by_id(usuario_id)
    usuario.rol = rol_efectivo(usuario.rol)
    return usuario
