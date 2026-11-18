# Kardex Agrícola — Monolito Modular (DDD)

Sistema para llevar el **Kardex Agrícola de hoja fresca**: planilla de cosechas,
entradas y salidas del almacén y el libro Kardex con **saldo automático**.

Incluye un **portal público para el productor (cliente)** donde cada productor
entra con su usuario y ve **solo su propia información**, en modo **solo lectura**.

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
3. Copia el archivo `.env.example` y renómbralo a `.env`. Cambia `SECRET_KEY` por una
   clave larga y propia.
4. Ejecuta:

```bash
docker compose up -d --build
```

La primera vez tarda un poco (descarga MySQL y phpMyAdmin). Después es rápido.

> Si ya tenías la base de datos de una versión anterior, **no se pierde nada**:
> al arrancar, la API agrega sola las columnas y tablas nuevas que falten.

---

## Cómo entrar

| Servicio | Dirección | Notas |
|---|---|---|
| **Portal del productor** | http://localhost:8001 | Registro libre y consulta del Kardex |
| API + documentación (Swagger) | http://localhost:8001/docs | Probar endpoints con token |
| Comprobación de la API | http://localhost:8001/health | Respuesta rápida |
| phpMyAdmin | http://localhost:8080 | Ver y editar tablas |

Datos para phpMyAdmin: **Servidor** `db`, **Usuario** `grupo3`, **Contraseña** `ciego123`
(también funciona con el usuario `root`).

---

## Perfiles del sistema

| Rol | Cómo se crea | Qué puede hacer |
|---|---|---|
| **admin** | Una sola vez con `/auth/bootstrap-admin` | Todo: usuarios, invitaciones, inventario, cosechas, Kardex |
| **encargado** | Con **código de invitación** | Inventario, cosecheros, cosechas y movimientos |
| **trabajador** | Con **código de invitación** | Consulta la información autorizada |
| **cliente** (productor) | **Registro libre** | Solo consulta su propio Kardex, sin editar nada |

Reglas de seguridad implementadas:

- Solo existe **un administrador principal**.
- El registro libre **siempre** crea un `cliente`; el formulario no permite elegir rol.
- Encargados y trabajadores necesitan una **invitación de un solo uso y con vencimiento**.
- Las contraseñas se guardan con **bcrypt** (con sal). Las cuentas viejas con SHA-256
  siguen entrando y su hash se actualiza solo al iniciar sesión.
- La sesión usa **token JWT**; los endpoints están protegidos por rol.
- Las claves van en `.env`, nunca en GitHub.

---

## Portal del productor (cliente)

1. Entra a **http://localhost:8001**
2. Pulsa **Crear cuenta** y regístrate (nombre, usuario y contraseña).
3. Al entrar verás tu panel con:
   - **Resumen:** fincas, hectáreas, kilos cosechados, monto en Bs y saldo en almacén.
   - **Mis fincas**
   - **Mis cosechas** (con filtro por texto y por fechas)
   - **Mi Kardex** (entradas, salidas y saldo)
   - **Mis lotes**
4. El botón **Imprimir** permite guardar todo como PDF.

> El productor **no puede crear, editar ni borrar nada**. El portal solo hace
> consultas (`GET`). Si intenta escribir, la API responde `403`.

### ¿Cómo ve un productor sus datos?

El administrador asocia cada **finca** a un usuario con rol `cliente`:

```http
POST /portal/api/admin/asignar-finca
Authorization: Bearer <token del admin>
Content-Type: application/json

{ "finca_id": 1, "usuario_id": 5 }
```

También se puede hacer al crear la finca:

```http
POST /inventario/fincas
{ "numero": 1, "nombre": "Finca El Rosal", "ubicacion": "Caraparí", "usuario_id": 5 }
```

Para ver qué clientes existen y qué fincas tienen:

```http
GET /portal/api/admin/clientes
Authorization: Bearer <token del admin>
```

El productor verá: sus fincas, las cosechas de esas fincas, los lotes de esas fincas
y los movimientos del Kardex de esas fincas.

---

## Primer administrador

En una instalación nueva todavía no hay administrador. Se crea **una sola vez**:

```http
POST /auth/bootstrap-admin
Content-Type: application/json

{ "username": "admin", "password": "unaClaveSegura", "nombre_completo": "Administrador General" }
```

Si ya existe un administrador, el endpoint responde `400` y no crea nada más.

---

## Invitaciones para encargado y trabajador

El administrador genera un código:

```http
POST /auth/invitaciones
Authorization: Bearer <token del admin>

{ "rol": "encargado", "dias_vigencia": 7 }
```

Respuesta:

```json
{ "id": 1, "codigo": "KX-9F3A21BC", "rol": "encargado", "expira_en": "2026-11-25T10:00:00", "usado": false, "activo": true }
```

La persona se registra con ese código:

```http
POST /auth/register-staff
{ "username": "juan", "password": "clave123", "nombre_completo": "Juan Pérez", "codigo_invitacion": "KX-9F3A21BC" }
```

El código **se vence** y **no se puede usar dos veces**.

---

## Cómo usar Swagger con token

1. Abre http://localhost:8001/docs
2. Ejecuta `POST /auth/login` con tu usuario y contraseña.
3. Copia el valor de `access_token`.
4. Pulsa el botón **Authorize** (arriba a la derecha), pega el token y acepta.
5. Ya puedes usar los endpoints protegidos.

---

## Endpoints principales

### Autenticación (`/auth`)

| Método | Ruta | Quién | Qué hace |
|---|---|---|---|
| POST | `/auth/register` | público | Registro libre (siempre cliente) |
| POST | `/auth/register-staff` | público + invitación | Registro de encargado/trabajador |
| POST | `/auth/bootstrap-admin` | público (una vez) | Crea el administrador principal |
| POST | `/auth/login` | público | Devuelve el token |
| GET | `/auth/me` | autenticado | Datos del usuario actual |
| GET | `/auth/usuarios` | admin | Lista usuarios |
| POST | `/auth/invitaciones` | admin | Crea invitación |
| GET | `/auth/invitaciones` | admin | Lista invitaciones |

### Portal del productor (`/portal/api`)

| Método | Ruta | Quién | Qué hace |
|---|---|---|---|
| GET | `/portal/api/resumen` | cliente | Totales de su producción |
| GET | `/portal/api/mis-fincas` | cliente | Sus fincas |
| GET | `/portal/api/mis-cosechas` | cliente | Sus cosechas |
| GET | `/portal/api/mi-kardex` | cliente | Entradas, salidas y saldo |
| GET | `/portal/api/mis-lotes` | cliente | Sus lotes |
| GET | `/portal/api/admin/clientes` | admin | Clientes y sus fincas |
| POST | `/portal/api/admin/asignar-finca` | admin | Asocia finca ↔ cliente |

### Inventario (`/inventario`)

| Método | Ruta | Quién |
|---|---|---|
| GET | `/inventario/fincas`, `/parcelas`, `/lotes` | autenticado |
| POST | `/inventario/fincas`, `/parcelas`, `/lotes` | admin / encargado |
| PUT | `/inventario/fincas/{id}/asignar` | admin |

### Cosechas y Kardex (`/kardex`, `/cosecheros`)

| Método | Ruta | Quién |
|---|---|---|
| GET | `/kardex/cosechas`, `/kardex/movimientos` | autenticado |
| POST | `/kardex/cosechas`, `/kardex/movimientos` | admin / encargado |
| GET | `/cosecheros` | autenticado |
| POST / PUT / DELETE | `/cosecheros` | admin / encargado |

---

## Comandos útiles

```bash
docker compose up -d          # encender todo
docker compose up -d --build  # reconstruir si cambias el código
docker compose ps             # ver qué está corriendo
docker compose logs -f web    # ver los mensajes de la API
docker compose down           # apagar (los datos se conservan)
```

---

## Estructura del proyecto

```text
KARDEX_monolitomodular/
├── docker-compose.yml     # Levanta MySQL, phpMyAdmin y la API
├── Dockerfile             # Receta del contenedor de la API
├── init.sql               # Crea las 8 tablas al iniciar MySQL
├── requeriment.txt        # Librerías que usa el proyecto
├── .env.example           # Ejemplo de configuración (copiar a .env)
└── src/
    ├── main.py            # Arranca la API, migra y sirve el portal
    ├── core/
    │   ├── config.py      # Lee el archivo .env
    │   ├── database.py    # Conexión con MySQL
    │   └── migrate.py     # Actualiza una base antigua sin perder datos
    ├── static/portal/     # Páginas del portal (HTML, CSS y JS)
    └── modules/           # Módulos con las 4 capas DDD
        ├── auth/          # Usuarios, login, roles e invitaciones
        ├── supliers/      # Cosecheros
        ├── inventory/     # Fincas, parcelas y lotes
        ├── kardex/        # Cosechas y movimientos del Kardex
        └── portal/        # Consultas de solo lectura del productor
```

Cada módulo dentro de `src/modules/` se divide en:

- `domain/` → reglas del negocio (entidades puras, sin base de datos).
- `application/` → casos de uso (servicios y validaciones).
- `infrastructure/` → conexión técnica (modelos SQLAlchemy y repositorios).
- `presentation/` → endpoints HTTP (routers de FastAPI).

---

## Tablas de la base de datos (`db_kardex`)

| Tabla | Contenido |
|---|---|
| `usuarios` | Usuario, contraseña (bcrypt) y rol |
| `invitaciones` | Códigos de un solo uso para encargado/trabajador |
| `cosecheros` | Personas que cosechan |
| `fincas` | Fincas (con `usuario_id` = productor dueño) |
| `parcelas` | Parcelas por finca, con hectáreas |
| `lotes` | Lotes de ingreso al almacén |
| `cosechas` | Planilla: fecha, cosechero, finca, kg y monto Bs. |
| `kardex_movimientos` | Libro: entrada_kg, salida_kg y saldo_kg |

**Regla del saldo automático:**

```text
saldo = saldo anterior + entrada_kg − salida_kg
```

---

## Aviso de seguridad

El archivo `.env` y las claves **no se suben** al repositorio (están en `.gitignore`).
Si vas a publicar este proyecto, cambia `tu_password_root` y `SECRET_KEY` por valores
propios, tanto en el `.env` como en `docker-compose.yml`.
