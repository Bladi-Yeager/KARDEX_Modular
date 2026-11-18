class UsuarioYaExiste(Exception):
    def __init__(self, username: str):
        self.username = username
        super().__init__(f"El usuario {username} ya existe")


class CredencialesInvalidas(Exception):
    def __init__(self):
        super().__init__("Usuario o contrasena incorrectos")


class UsuarioInactivo(Exception):
    def __init__(self):
        super().__init__("El usuario esta inactivo. Contacta al administrador.")


class InvitacionInvalida(Exception):
    def __init__(self, motivo: str = "El codigo de invitacion no es valido"):
        super().__init__(motivo)


class RolInvalido(Exception):
    def __init__(self, rol: str):
        self.rol = rol
        super().__init__(
            f"Rol '{rol}' no permitido. Usa: admin, encargado, trabajador o cliente."
        )


class AdminYaExiste(Exception):
    def __init__(self):
        super().__init__(
            "Ya existe un administrador principal. El administrador se crea una sola vez."
        )
