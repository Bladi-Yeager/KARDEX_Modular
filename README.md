# Kardex Agrícola (Monolito Modular - DDD)

Servidor para llevar el control del **Kardex Agrícola de hoja fresca**: planilla de
cosechas, entradas y salidas del almacén y el libro Kardex con saldo automático.

Hecho con **FastAPI + SQLAlchemy + MySQL 8 + Docker**. El código está organizado por
módulos y cada módulo tiene 4 capas (arquitectura DDD).

---

## ¿Qué necesitas para levantarlo?

Solo tener instalado **Docker Desktop**. No hace falta instalar Python ni MySQL por
separado, Docker se encarga de todo.

---

## Cómo levantarlo paso a paso

1. Descarga o clona esta carpeta.
2. Abre una terminal **dentro de la carpeta** del proyecto.
3. Copia el archivo `.env.example` y renómbralo a `.env`, y cambia la clave por una tuya.
4. Ejecuta:

```bash
docker compose up -d --build
```

La primera vez tarda un poco (descarga MySQL y phpMyAdmin). Después es rápido.

---

## Cómo entrar

| Servicio | Dirección | Notas |
|---|---|---|
| API + documentación (Swagger) | http://localhost:8001/docs | Probar y registrar datos |
| API (raíz) | http://localhost:8001/ | Comprobación rápida |
| phpMyAdmin | http://localhost:8080 | Ver y editar tablas |

Datos para phpMyAdmin: **Servidor** `db`, **Usuario** `grupo3`, **Contraseña** `ciego123`
(también funciona con el usuario `root`).

Usuario de la API: `grupo3` / `ciego123`.

---

## Comandos útiles

```bash
docker compose up -d          # encender todo
docker compose up -d --build  # reconstruir si cambias el código
docker compose ps             # ver qué está corriendo
docker compose down           # apagar (los datos se conservan)
```

---

## Estructura del proyecto

```text
KARDEX_monolitomodular/
├── docker-compose.yml     # Levanta MySQL, phpMyAdmin y la API
├── Dockerfile             # Receta del contenedor de la API
├── init.sql               # Crea las 7 tablas al iniciar MySQL
├── requeriment.txt        # Librerías que usa el proyecto
├── .env.example           # Ejemplo de configuración (copiar a .env)
└── src/
    ├── main.py            # Arranca la API y registra los módulos
    ├── core/
    │   ├── config.py      # Lee el archivo .env
    │   └── database.py    # Conexión con MySQL
    └── modules/           # Módulos con las 4 capas DDD
        ├── auth/          # Usuarios, registro y login
        ├── supliers/      # Cosecheros
        ├── inventory/     # Fincas, parcelas y lotes
        └── kardex/        # Cosechas y movimientos del Kardex
```

Cada módulo dentro de `src/modules/` se divide en:

- `domain/` → reglas del negocio (entidades puras, sin base de datos).
- `application/` → casos de uso (servicios y validaciones).
- `infrastructure/` → conexión técnica (modelos SQLAlchemy y repositorios).
- `presentation/` → endpoints HTTP (routers de FastAPI).

---

## Módulos y rutas

| Módulo | Ruta base | Para qué sirve |
|---|---|---|
| auth | `/auth` | Usuarios, registro y login |
| supliers | `/cosecheros` | Lista de cosecheros |
| inventory | `/inventario` | Fincas, parcelas y lotes |
| kardex | `/kardex` | Cosechas y libro Kardex |

---

## Tablas de la base de datos (`db_kardex`)

| Tabla | Contenido |
|---|---|
| `usuarios` | Usuario, contraseña y rol |
| `cosecheros` | Personas que cosechan |
| `fincas` | Fincas |
| `parcelas` | Parcelas por finca, con hectáreas |
| `lotes` | Lotes de ingreso al almacén |
| `cosechas` | Planilla: fecha, cosechero, finca, kg y monto Bs. |
| `kardex_movimientos` | Libro: entrada_kg, salida_kg y saldo_kg |

---

## Aviso de seguridad

El archivo `.env` y las claves **no se suben** al repositorio (están en `.gitignore`).
Si vas a publicar este proyecto, cambia la contraseña `tu_password_root` por una tuya
tanto en el `.env` como en el `docker-compose.yml`.
