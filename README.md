# Kardex Agrícola

Aplicación web para centros de acopio del Trópico de Cochabamba. Permite
registrar las entregas de cada chaco, rastrear sus lotes y conciliar las
existencias por producto. Cada instalación representa una empresa.
El sistema usa FastAPI, SQLAlchemy, MySQL y Docker Compose.

## Arranque

1. En esta carpeta, crea `.env` a partir de `.env.example` si todavía no existe.
   Configura `MYSQL_PASSWORD` y `MYSQL_ROOT_PASSWORD` con las claves del volumen (o claves nuevas si es la primera instalación). Configura una `SECRET_KEY` aleatoria de al menos 32 caracteres para conservar
   las sesiones después de reiniciar. Conserva la conexión y el volumen MySQL de
   tu instalación, y revisa las credenciales antes de exponer el servicio.
2. Ejecuta `docker compose up -d --build`.
3. Crea las cuentas de instalación desde una terminal autorizada del servidor:

   ```sh
   docker compose exec web python -m src.core.provision jefe direccion "Nombre del jefe"
   docker compose exec web python -m src.core.provision soporte soporte_local "Nombre de soporte"
   ```

   El comando solicita la contraseña de forma interactiva. El jefe crea al
   administrador operativo desde **Cuentas**. Las cuentas existentes de admin o
   encargado se reconocen como administradores operativos. Las cuentas históricas de trabajador acceden al portal de solo lectura con sus credenciales y ven únicamente sus fincas asignadas.
4. Abre `http://localhost:8001`. El panel interno está en `/admin` y el portal
   de productores en `/portal`.

Para una base vacía de demostración puedes activar `DEMO_DATA=true`.
El diagnóstico con phpMyAdmin es opcional y local. Para habilitarlo ejecuta
`docker compose --profile diagnostico up -d phpmyadmin`.

## Solicitudes de acceso

Desde el portal, el productor elige su contraseña y solicita acceso. El administrador recibe un aviso en el panel y aprueba la solicitud en **Afiliaciones**, vinculándola a un chaco activo sin asignar. La aprobación habilita el primer ingreso. Una cuenta creada directamente por el administrador puede ingresar inmediatamente. El portal incluye el enlace de soporte por WhatsApp.

## Perfiles

| Perfil | Operaciones |
| --- | --- |
| Soporte técnico | Ver el estado de los servicios y descargar su diagnóstico. |
| Jefe | Consultar el resultado financiero exclusivo por lote y período, además de producción y existencias. Crear y gestionar accesos de administradores. |
| Administrador operativo | Registrar fincas, parcelas, cosechas, lotes, movimientos, ventas y costos. Gestionar productores y afiliaciones. |
| Productor afiliado | Consultar y descargar los registros de sus fincas asignadas. |

Los registros de finca se muestran a la cuenta asociada actualmente. Revisa la
asignación antes de transferir una finca, porque la cuenta que recibe la
asignación podrá consultar su historial.

## Flujo de trabajo

1. En **Productos y unidades**, el administrador administra el catálogo.
   El punto de partida es piña por piezas, banano por cajas y pitahaya por kg.
   Para una operación de piña pesada, se puede crear otra presentación en kg.
   Cada presentación lleva su propio saldo. Usa la unidad principal con la que
   se recibe y se despacha. Las piezas y cajas se registran como enteros.
2. En **Cosechas**, registra un borrador con producto, chaco, cosechero y
   cantidad estimada. Puede editarse o eliminarse antes de confirmar.
3. En **Recibir**, escribe el lote, la cantidad que llegó y la que se rechazó.
   Un rechazo requiere motivo. La medición adicional es opcional y se refiere
   al total que llegó. La recepción registra el lote y solo la parte aceptada
   entra al Kardex. Un rechazo total conserva su comprobante y genera cero
   existencias. El productor consulta e imprime su comprobante desde **Mis entregas**.
4. En **Kardex**, selecciona el lote para despachar o registrar una merma.
   El lote determina el producto y su unidad. La salida debe respetar el saldo
   del producto, chaco y lote. Una anulación conserva el movimiento original y
   registra una compensación.
5. En **Ventas y costos**, el administrador registra los importes. El resumen
   del jefe muestra la diferencia registrada para el período cuando hay ambos
   tipos de datos. El resultado depende de los importes cargados. Una venta se
   registra en finanzas y el despacho correspondiente se registra en Kardex.
6. **Cierre de hoy** muestra el saldo inicial, lo recibido y rechazado, las
   entradas, las salidas, la merma neta y el saldo de cada producto. Es una
   consulta por fecha. Selecciona una tarjeta para abrir el detalle.
7. **Descargar Excel** genera el archivo `.xlsx` con la tabla autorizada y los
   filtros de la vista. El productor también puede imprimir desde el navegador.

## Actualizar una instalación

Haz un respaldo del volumen MySQL antes de desplegar. El arranque agrega las
columnas del catálogo, la recepción y las cantidades. Las consultas recalculan
el saldo histórico a partir de entradas y salidas. Los registros anteriores
sin producto aparecen como **Histórico sin clasificar**, separado del catálogo
nuevo. Un borrador histórico se puede clasificar al editarlo. Las mediciones
secundarias se guardan por separado. El sistema no aplica una equivalencia
general de cajas o piezas a kilos.

Las invitaciones antiguas se conservan como datos históricos. El alta del
propietario y de soporte se realiza desde el servidor. Si una base antigua
contiene una columna obligatoria adicional en `cosechas`, revisa esa columna
antes de registrar datos nuevos.

## Comprobaciones locales

Instala las dependencias y ejecuta la prueba de regresión de API con SQLite:

```sh
python -m pip install -r requeriment.txt httpx
python -m unittest discover -s tests -v
```

La documentación interactiva de la API está en `/docs`.
