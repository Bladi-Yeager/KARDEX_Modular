import secrets
from datetime import datetime, timedelta

from src.modules.auth.application.dtos import (
    ClienteRegister,
    InvitacionCreate,
    StaffRegister,
    UsuarioLogin,
)
from src.modules.auth.domain.exceptions import (
    AdminYaExiste,
    CredencialesInvalidas,
    InvitacionInvalida,
    RolInvalido,
    SolicitudPendiente,
    UsuarioInactivo,
    UsuarioYaExiste,
)
from src.modules.auth.domain.models import ROLES_VALIDOS, Invitacion, Usuario, rol_efectivo
from src.modules.auth.domain.repositories import InvitacionRepository, UsuarioRepository
from src.modules.auth.infrastructure.external_adapters import PasswordHasher
from src.modules.auth.infrastructure.tokens import create_access_token

ROLES_CON_INVITACION = ("encargado", "trabajador")


class AuthService:
    def __init__(self, repository: UsuarioRepository):
        self.repository = repository

    # ------------------------------------------------------------------ utilidades
    def _crear(self, data, rol: str) -> Usuario:
        if self.repository.exists_username(data.username):
            raise UsuarioYaExiste(data.username)
        usuario = Usuario(
            username=data.username.strip(),
            password_hash=PasswordHasher.hash(data.password),
            nombre_completo=data.nombre_completo.strip(),
            rol=rol,
            activo=rol != "pendiente",
        )
        return self.repository.add(usuario)

    def list_all(self):
        return self.repository.list_all()

    # ------------------------------------------------------------------ registros
    def register_cliente(self, data: ClienteRegister) -> Usuario:
        """Reserva el usuario hasta que un administrador apruebe su afiliación."""
        return self._crear(data, "pendiente")

    def register_staff(self, data: StaffRegister, invitacion: Invitacion) -> Usuario:
        """Registro con invitacion: el rol lo manda la invitacion, no el formulario."""
        if invitacion.rol not in ROLES_CON_INVITACION:
            raise InvitacionInvalida("La invitacion no permite ese rol")
        if not invitacion.esta_vigente():
            raise InvitacionInvalida(
                "El codigo de invitacion ya fue usado o esta vencido"
            )
        return self._crear(data, invitacion.rol)

    def bootstrap_admin(self, data) -> Usuario:
        """Crea el unico administrador principal, solo si todavia no existe ninguno."""
        if self.repository.exists_admin():
            raise AdminYaExiste()
        return self._crear(data, "admin")

    def crear_usuario(self, data, rol_actor: str) -> Usuario:
        rol = (data.rol or "cliente").strip().lower()
        permitido = {"jefe": "admin", "admin": "cliente"}.get(rol_actor)
        if rol != permitido:
            raise RolInvalido(data.rol)
        return self._crear(data, rol)

    def provisionar(self, data, rol: str) -> Usuario:
        if rol not in ("jefe", "soporte"):
            raise RolInvalido(rol)
        return self._crear(data, rol)

    # ------------------------------------------------------------------ login
    def login(self, data: UsuarioLogin) -> dict:
        usuario = self.repository.get_by_username(data.username.strip())
        if not usuario or not PasswordHasher.verify(data.password, usuario.password_hash):
            raise CredencialesInvalidas()
        if usuario.rol == "pendiente":
            raise SolicitudPendiente()
        usuario.rol = rol_efectivo(usuario.rol)
        if not usuario.activo or usuario.rol not in ROLES_VALIDOS:
            raise UsuarioInactivo()

        # Si el usuario venia de la version vieja (SHA-256), subimos su hash.
        if PasswordHasher.needs_rehash(usuario.password_hash):
            self.repository.update_password_hash(
                usuario.id, PasswordHasher.hash(data.password)
            )

        return {
            "access_token": create_access_token(usuario),
            "token_type": "bearer",
            "usuario": usuario,
        }


class InvitacionService:
    def __init__(self, repository: InvitacionRepository):
        self.repository = repository

    def crear(self, data: InvitacionCreate, creado_por: int | None) -> Invitacion:
        rol = data.rol.strip().lower()
        if rol not in ROLES_CON_INVITACION:
            raise RolInvalido(data.rol)

        codigo = self._generar_codigo()
        invitacion = Invitacion(
            codigo=codigo,
            rol=rol,
            activo=rol != "pendiente",
            creado_por=creado_por,
            expira_en=datetime.now() + timedelta(days=data.dias_vigencia),
        )
        return self.repository.add(invitacion)

    def _generar_codigo(self) -> str:
        for _ in range(20):
            codigo = "KX-" + secrets.token_hex(4).upper()
            if not self.repository.exists_codigo(codigo):
                return codigo
        raise RuntimeError("No se pudo generar un codigo de invitacion unico")

    def listar(self):
        return self.repository.list_all()

    def obtener_vigente(self, codigo: str) -> Invitacion:
        invitacion = self.repository.get_by_codigo(codigo)
        if invitacion is None:
            raise InvitacionInvalida("El codigo de invitacion no existe")
        if not invitacion.esta_vigente():
            raise InvitacionInvalida(
                "El codigo de invitacion ya fue usado o esta vencido"
            )
        return invitacion

    def marcar_usada(self, invitacion: Invitacion, usuario_id: int) -> None:
        self.repository.marcar_usada(invitacion.id, usuario_id)
