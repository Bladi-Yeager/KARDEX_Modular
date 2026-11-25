"""Alta de perfiles de instalación con acceso autorizado al servidor."""

from argparse import ArgumentParser
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from src.core.database import SessionLocal
from src.modules.auth.application.dtos import ClienteRegister
from src.modules.auth.application.services import AuthService
from src.modules.auth.domain.exceptions import UsuarioYaExiste
from src.modules.auth.infrastructure.repository_impl import UsuarioRepositoryImpl


def main():
    parser = ArgumentParser(description="Crear una cuenta de jefe o soporte técnico.")
    parser.add_argument("rol", choices=("jefe", "soporte", "admin"))
    parser.add_argument("usuario")
    parser.add_argument("nombre")
    args = parser.parse_args()
    password = getpass("Contraseña (al menos 12 caracteres): ")
    if len(password) < 12 or password != getpass("Confirma la contraseña: "):
        parser.error("La contraseña debe tener al menos 12 caracteres y coincidir.")
    with SessionLocal() as db:
        try:
            data = ClienteRegister(username=args.usuario, nombre_completo=args.nombre, password=password)
            AuthService(UsuarioRepositoryImpl(db)).provisionar(data, args.rol)
        except ValidationError:
            parser.error("Revisa la longitud del nombre de usuario, nombre y contraseña.")
        except (UsuarioYaExiste, IntegrityError):
            parser.error("El nombre de usuario ya existe.")
    print(f"Cuenta {args.rol} creada.")


if __name__ == "__main__":
    main()
