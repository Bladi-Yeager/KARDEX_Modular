-- ============================================================
-- KARDEX AGRICOLA - Hoja Fresca
-- Base de datos: db_kardex
-- ============================================================

CREATE DATABASE IF NOT EXISTS db_kardex CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE db_kardex;

-- ============================================================
-- auth
-- Roles del sistema:
--   admin      -> administrador principal (uno solo)
--   encargado  -> administra la operacion de la finca
--   trabajador -> registra y consulta sus actividades
--   cliente    -> productor: SOLO consulta su propio Kardex
-- ============================================================
CREATE TABLE IF NOT EXISTS usuarios (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(50)  NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(100) NOT NULL,
    rol             VARCHAR(32)  NOT NULL DEFAULT 'cliente',
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- supliers
CREATE TABLE IF NOT EXISTS cosecheros (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    nombre     VARCHAR(100) NOT NULL,
    ci         VARCHAR(20)  NULL,
    telefono   VARCHAR(20)  NULL,
    usuario_id INT NULL,
    activo     BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- ============================================================
-- INVENTARIO
-- ============================================================
CREATE TABLE IF NOT EXISTS fincas (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    numero     INT NOT NULL UNIQUE,
    nombre     VARCHAR(100) NULL,
    ubicacion  VARCHAR(150) NULL,
    usuario_id INT NULL,
    activo     BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS parcelas (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    finca_id       INT NOT NULL,
    numero         INT NOT NULL,
    superficie_ha  DECIMAL(10,2) NULL,
    activo         BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE KEY uq_parcela (finca_id, numero),
    FOREIGN KEY (finca_id) REFERENCES fincas(id)
);

CREATE TABLE IF NOT EXISTS lotes (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    codigo        VARCHAR(30) NOT NULL UNIQUE,
    finca_id      INT NULL,
    fecha_ingreso DATE NOT NULL,
    detalle       VARCHAR(150) NULL,
    creado_en     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (finca_id) REFERENCES fincas(id)
);

-- ============================================================
-- KARDEX
-- ============================================================
CREATE TABLE IF NOT EXISTS cosechas (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    fecha         DATE NOT NULL,
    cosechero_id  INT NOT NULL,
    finca_id      INT NOT NULL,
    parcela_id    INT NULL,
    tipo_cosecha  VARCHAR(50) NOT NULL DEFAULT 'HOJA FRESCA',
    kg            DECIMAL(12,3) NOT NULL,
    monto_bs      DECIMAL(12,2) NOT NULL DEFAULT 0,
    observacion   VARCHAR(200) NULL,
    FOREIGN KEY (cosechero_id) REFERENCES cosecheros(id),
    FOREIGN KEY (finca_id)     REFERENCES fincas(id),
    FOREIGN KEY (parcela_id)   REFERENCES parcelas(id)
);

CREATE TABLE IF NOT EXISTS kardex_movimientos (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    fecha       DATE NOT NULL,
    detalle     VARCHAR(150) NOT NULL,
    doc         VARCHAR(30) NULL,
    lote_id     INT NULL,
    finca_id    INT NULL,
    entrada_kg  DECIMAL(12,3) NOT NULL DEFAULT 0,
    salida_kg   DECIMAL(12,3) NOT NULL DEFAULT 0,
    saldo_kg    DECIMAL(12,3) NOT NULL DEFAULT 0,
    observacion VARCHAR(200) NULL,
    FOREIGN KEY (lote_id)  REFERENCES lotes(id),
    FOREIGN KEY (finca_id) REFERENCES fincas(id)
);

-- ============================================================
-- INVITACIONES (solo para encargado y trabajador)
-- Un solo uso, con vencimiento.
-- ============================================================
CREATE TABLE IF NOT EXISTS invitaciones (
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
);

-- INDICES para busquedas frecuentes por fecha y finca
CREATE INDEX idx_cosechas_fecha      ON cosechas(fecha);
CREATE INDEX idx_cosechas_finca      ON cosechas(finca_id);
CREATE INDEX idx_cosechas_cosechero  ON cosechas(cosechero_id);
CREATE INDEX idx_kardex_fecha        ON kardex_movimientos(fecha);
CREATE INDEX idx_kardex_lote         ON kardex_movimientos(lote_id);
CREATE INDEX idx_fincas_usuario      ON fincas(usuario_id);
CREATE INDEX idx_cosecheros_usuario  ON cosecheros(usuario_id);
