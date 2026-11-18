import hashlib

import bcrypt

# bcrypt solo usa los primeros 72 bytes de la contrasena.
_MAX_BYTES = 72


def _prepare(password: str) -> bytes:
    return password.encode("utf-8")[:_MAX_BYTES]


class PasswordHasher:
    """Hashing seguro de contrasenas.

    Las contrasenas nuevas se guardan con bcrypt (con sal aleatoria).
    Las contrasenas viejas guardadas con SHA-256 simple se siguen aceptando
    para no dejar fuera a los usuarios que ya existian; cuando uno de ellos
    inicia sesion, su hash se actualiza solo a bcrypt.
    """

    @staticmethod
    def hash(password: str) -> str:
        return bcrypt.hashpw(_prepare(password), bcrypt.gensalt(rounds=12)).decode("utf-8")

    @staticmethod
    def verify(password: str, password_hash: str) -> bool:
        if not password_hash:
            return False
        if password_hash.startswith(("$2a$", "$2b$", "$2y$")):
            try:
                return bcrypt.checkpw(_prepare(password), password_hash.encode("utf-8"))
            except ValueError:
                return False
        # Compatibilidad con los hashes SHA-256 antiguos.
        legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return legacy == password_hash

    @staticmethod
    def needs_rehash(password_hash: str) -> bool:
        return not password_hash.startswith(("$2a$", "$2b$", "$2y$"))
