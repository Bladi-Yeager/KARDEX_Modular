from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from src.modules.auth.domain.models import Invitacion, Usuario
from src.modules.auth.infrastructure.models_db import InvitacionDB, UsuarioDB


class UsuarioRepositoryImpl:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _to_domain(row: UsuarioDB) -> Usuario:
        return Usuario(
            id=row.id,
            username=row.username,
            password_hash=row.password_hash,
            nombre_completo=row.nombre_completo,
            rol=row.rol,
            activo=row.activo,
        )

    def list_all(self) -> List[Usuario]:
        rows = self.db.query(UsuarioDB).order_by(UsuarioDB.id).all()
        return [self._to_domain(row) for row in rows]

    def get_by_id(self, usuario_id: int) -> Optional[Usuario]:
        row = self.db.query(UsuarioDB).get(usuario_id)
        return self._to_domain(row) if row else None

    def get_by_username(self, username: str) -> Optional[Usuario]:
        row = self.db.query(UsuarioDB).filter(UsuarioDB.username == username).first()
        return self._to_domain(row) if row else None

    def exists_username(self, username: str) -> bool:
        return (
            self.db.query(UsuarioDB).filter(UsuarioDB.username == username).first()
            is not None
        )

    def exists_admin(self) -> bool:
        return (
            self.db.query(UsuarioDB)
            .filter(UsuarioDB.rol == "admin", UsuarioDB.activo.is_(True))
            .first()
            is not None
        )

    def add(self, usuario: Usuario) -> Usuario:
        row = UsuarioDB(
            username=usuario.username,
            password_hash=usuario.password_hash,
            nombre_completo=usuario.nombre_completo,
            rol=usuario.rol,
            activo=usuario.activo,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._to_domain(row)

    def update_password_hash(self, usuario_id: int, password_hash: str) -> None:
        row = self.db.query(UsuarioDB).get(usuario_id)
        if row is not None:
            row.password_hash = password_hash
            self.db.commit()


class InvitacionRepositoryImpl:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _to_domain(row: InvitacionDB) -> Invitacion:
        return Invitacion(
            id=row.id,
            codigo=row.codigo,
            rol=row.rol,
            creado_por=row.creado_por,
            usado_por=row.usado_por,
            expira_en=row.expira_en,
            usado_en=row.usado_en,
            activo=row.activo,
        )

    def list_all(self) -> List[Invitacion]:
        rows = self.db.query(InvitacionDB).order_by(InvitacionDB.id.desc()).all()
        return [self._to_domain(row) for row in rows]

    def get_by_codigo(self, codigo: str) -> Optional[Invitacion]:
        row = (
            self.db.query(InvitacionDB)
            .filter(InvitacionDB.codigo == codigo.strip().upper())
            .first()
        )
        return self._to_domain(row) if row else None

    def exists_codigo(self, codigo: str) -> bool:
        return self.get_by_codigo(codigo) is not None

    def add(self, invitacion: Invitacion) -> Invitacion:
        row = InvitacionDB(
            codigo=invitacion.codigo,
            rol=invitacion.rol,
            creado_por=invitacion.creado_por,
            expira_en=invitacion.expira_en,
            activo=invitacion.activo,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._to_domain(row)

    def marcar_usada(self, invitacion_id: int, usuario_id: int) -> None:
        row = self.db.query(InvitacionDB).get(invitacion_id)
        if row is not None:
            row.usado_por = usuario_id
            row.usado_en = datetime.now()
            row.activo = False
            self.db.commit()
