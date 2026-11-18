"""Migraciones ligeras que se ejecutan al arrancar la API.

Sirven para que una base de datos que ya existia (con el volumen de MySQL
anterior) se actualice sola sin perder datos: agrega columnas y tablas nuevas
solo si no estan. Es idempotente: se puede ejecutar muchas veces.
"""

from sqlalchemy import text

from src.core.database import engine


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
        # 1) El rol pasa de ENUM cerrado a texto, para poder tener
        #    admin / encargado / trabajador / cliente sin romper la tabla.
        conn.execute(
            text(
                "ALTER TABLE usuarios MODIFY rol VARCHAR(32) NOT NULL DEFAULT 'cliente'"
            )
        )

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

        # 5) Limpieza: una version anterior de la tabla cosechas traia una
        #    columna suelta llamada 'bladi' (NOT NULL, sin valor por defecto)
        #    que impedia registrar cosechas. Ya no se usa: se elimina.
        if _column_exists(conn, "cosechas", "bladi"):
            conn.execute(text("ALTER TABLE cosechas DROP COLUMN bladi"))
