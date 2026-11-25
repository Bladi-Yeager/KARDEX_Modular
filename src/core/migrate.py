"""Migraciones ligeras que se ejecutan al arrancar la API.

Sirven para que una base de datos que ya existia (con el volumen de MySQL
anterior) se actualice sola sin perder datos: agrega columnas y tablas nuevas
solo si no estan. Es idempotente: se puede ejecutar muchas veces.
"""

from sqlalchemy import inspect, text

from src.core.database import engine

CATALOGO_INICIAL = (
    {"nombre": "Piña", "unidad": "unidad"},
    {"nombre": "Banano", "unidad": "caja"},
    {"nombre": "Pitahaya", "unidad": "kg"},
)


def _migrar_acopio(conn):
    campos = {
        "registros_financieros": {"lote_id": "INT NULL"},
        "cosechas": {
            "producto_id": "INT NULL", "cantidad": "DECIMAL(12,3) NULL",
            "recibida": "DECIMAL(12,3) NULL", "rechazada": "DECIMAL(12,3) NULL",
            "motivo_rechazo": "VARCHAR(200) NULL", "cantidad_secundaria": "DECIMAL(12,3) NULL",
            "unidad_secundaria": "VARCHAR(10) NULL", "documento_recepcion": "VARCHAR(30) NULL",
        },
        "lotes": {"producto_id": "INT NULL"},
        "kardex_movimientos": {
            "cantidad_entrada": "DECIMAL(12,3) NULL", "cantidad_salida": "DECIMAL(12,3) NULL",
            "tipo": "VARCHAR(12) NULL",
        },
    }
    sqlite = conn.dialect.name == "sqlite"
    for tabla, columnas in campos.items():
        existentes = {col["name"] for col in inspect(conn).get_columns(tabla)}
        for campo, tipo in columnas.items():
            if campo in existentes:
                continue
            sql = f"ALTER TABLE {tabla} ADD COLUMN {campo} {tipo}"
            if campo == "lote_id":
                sql += " REFERENCES lotes(id)" if sqlite else ", ADD FOREIGN KEY (lote_id) REFERENCES lotes(id)"
            if campo == "producto_id":
                sql += " REFERENCES productos(id)" if sqlite else ", ADD FOREIGN KEY (producto_id) REFERENCES productos(id)"
            conn.execute(text(sql))
    insertar = "INSERT OR IGNORE" if sqlite else "INSERT IGNORE"
    conn.execute(text(f"{insertar} INTO productos (nombre, unidad) VALUES (:nombre, :unidad)"), list(CATALOGO_INICIAL))


def _table_exists(conn, tabla: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t
                """
            ),
            {"t": tabla},
        ).scalar()
    )


def _column_exists(conn, tabla: str, columna: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = :t AND COLUMN_NAME = :c
                """
            ),
            {"t": tabla, "c": columna},
        ).scalar()
    )


def _index_exists(conn, tabla: str, indice: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = :t AND INDEX_NAME = :i
                """
            ),
            {"t": tabla, "i": indice},
        ).scalar()
    )


def run_migrations() -> None:
    with engine.begin() as conn:
        if conn.dialect.name == "sqlite":
            conn.execute(text("INSERT OR IGNORE INTO kardex_control (id, revision) VALUES (1, 0)"))
            _migrar_acopio(conn)
            return

        # 1) El rol pasa de ENUM cerrado a texto, para poder tener
        #    admin / encargado / trabajador / cliente sin romper la tabla.
        columnas = {col["name"]: col for col in inspect(conn).get_columns("usuarios")}
        if columnas["rol"]["type"].__class__.__name__ == "ENUM":
            conn.execute(text("ALTER TABLE usuarios MODIFY rol VARCHAR(32) NOT NULL DEFAULT 'cliente'"))

        # 2) Dueno de cada finca (el productor / cliente).
        if not _column_exists(conn, "fincas", "usuario_id"):
            conn.execute(text("ALTER TABLE fincas ADD COLUMN usuario_id INT NULL"))
        if not _index_exists(conn, "fincas", "idx_fincas_usuario"):
            conn.execute(text("CREATE INDEX idx_fincas_usuario ON fincas(usuario_id)"))

        # 3) Vinculo opcional del cosechero con un usuario del sistema.
        if not _column_exists(conn, "cosecheros", "usuario_id"):
            conn.execute(text("ALTER TABLE cosecheros ADD COLUMN usuario_id INT NULL"))
        if not _index_exists(conn, "cosecheros", "idx_cosecheros_usuario"):
            conn.execute(
                text("CREATE INDEX idx_cosecheros_usuario ON cosecheros(usuario_id)")
            )

        # 4) Invitaciones de un solo uso para encargados y trabajadores.
        if not _table_exists(conn, "invitaciones"):
            conn.execute(
                text(
                    """
                    CREATE TABLE invitaciones (
                        id          INT AUTO_INCREMENT PRIMARY KEY,
                        codigo      VARCHAR(40) NOT NULL UNIQUE,
                        rol         VARCHAR(32) NOT NULL,
                        creado_por  INT NULL,
                        usado_por   INT NULL,
                        expira_en   DATETIME NOT NULL,
                        usado_en    DATETIME NULL,
                        activo      BOOLEAN NOT NULL DEFAULT TRUE,
                        creado_en   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (creado_por) REFERENCES usuarios(id),
                        FOREIGN KEY (usado_por)  REFERENCES usuarios(id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
            )

        if not _column_exists(conn, "cosechas", "borrador"):
            conn.execute(text("ALTER TABLE cosechas ADD borrador BOOLEAN NOT NULL DEFAULT FALSE"))
        if not _column_exists(conn, "lotes", "cosecha_id"):
            conn.execute(text(
                "ALTER TABLE lotes ADD cosecha_id INT NULL UNIQUE, "
                "ADD FOREIGN KEY (cosecha_id) REFERENCES cosechas(id)"
            ))
        if not _column_exists(conn, "kardex_movimientos", "anula_movimiento_id"):
            conn.execute(text(
                "ALTER TABLE kardex_movimientos ADD anula_movimiento_id INT NULL UNIQUE, "
                "ADD FOREIGN KEY (anula_movimiento_id) REFERENCES kardex_movimientos(id)"
            ))
        if not _column_exists(conn, "kardex_movimientos", "registrado_por"):
            conn.execute(text(
                "ALTER TABLE kardex_movimientos ADD registrado_por INT NULL, "
                "ADD FOREIGN KEY (registrado_por) REFERENCES usuarios(id)"
            ))
        conn.execute(text(
            "INSERT INTO kardex_control (id, revision) VALUES (1, 0) ON DUPLICATE KEY UPDATE id = id"
        ))
        _migrar_acopio(conn)
