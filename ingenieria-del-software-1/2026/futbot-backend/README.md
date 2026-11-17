# FutBot — Backend

API del juego FutBot: un juego multijugador de fútbol en el que los futbolistas no se controlan con teclado ni mouse, sino con comportamientos programados en Python por los propios usuarios.

Este repositorio implementa el manejo de datos y la lógica de negocio. La interfaz de usuario vive en [futbot-frontend](https://github.com/IngSoft1-los-transistores/futbot-frontend).

**Materia:** Ingeniería de Software I· **Equipo:** Los Transistores


## Stack

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.11+ |
| Framework | FastAPI |
| Servidor | Uvicorn |
| ORM | SQLAlchemy 2.0 |
| Validación | Pydantic v2 |
| Base de datos | SQLite (desarrollo) |
| Tests | pytest + httpx |

## Requisitos previos

- **Python 3.11 o superior** — verificar con `python --version` (en Linux y macOS puede ser `python3 --version`)
- **Git**

## Instalación

**1. Clonar el repositorio**

```bash
git clone https://github.com/IngSoft1-los-transistores/futbot-backend.git
cd futbot-backend
```

**2. Crear y activar el entorno virtual**

Linux, macOS o Git Bash en Windows:

```bash
python -m venv .venv
source .venv/bin/activate
```

PowerShell en Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

> Si PowerShell bloquea el script, ejecutar una vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

Cuando el entorno está activo, el prompt muestra `(.venv)` al principio. **Todos los comandos siguientes se ejecutan con el entorno activo.**

**3. Instalar las dependencias**

```bash
pip install -r requirements.txt
```

**4. Configurar las variables de entorno**

```bash
cp .env.example .env
```

Abrir el `.env` y cambiar `JWT_SECRET_KEY` por una cadena aleatoria. Para generar una:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

El archivo `.env` **no se sube al repositorio**: contiene secretos y es propio de cada máquina.

## Comandos rápidos con make

El `Makefile` de la raíz agrupa los comandos de uso diario. Usa directamente el Python del `.venv`, así que **no hace falta activar el entorno virtual** para correrlos.

**Instalar make**

| Sistema | Cómo |
|---|---|
| Linux / WSL | `sudo apt install make` (en Ubuntu suele venir instalado) |
| macOS | `xcode-select --install` |
| Windows | `winget install ezwinports.make` y reiniciar la terminal |

Funciona igual desde PowerShell, Git Bash, WSL, Linux y macOS.

**Comandos**

| Comando | Qué hace |
|---|---|
| `make help` | Lista los comandos disponibles |
| `make install` | Crea el `.venv` si no existe e instala las dependencias |
| `make reinstall` | Borra el `.venv` y lo crea de cero |
| `make dev` | Levanta la API en http://localhost:8000 con recarga automática |
| `make dev PORT=8001` | Lo mismo, en otro puerto |
| `make test` | Corre los tests y muestra la cobertura en la terminal |
| `make coverage` | Igual que `make test`, y además genera el reporte en `htmlcov/index.html` |
| `make lint` | Revisa el código con [Ruff](https://docs.astral.sh/ruff/) (reglas en `ruff.toml`) |
| `make clean` | Borra cachés y reportes. No toca `.env`, `.venv` ni `futbot.db` |

`make test` devuelve código de salida distinto de 0 si algún test falla, así que sirve para CI.

**Windows y WSL:** el `.venv` es propio de cada sistema, así que uno creado desde Windows no funciona en WSL ni al revés. Si se usa WSL, clonar el repo dentro de WSL (por ejemplo en `~/`), no trabajar sobre `/mnt/c/...`: además de evitar el problema, es mucho más rápido. `make reinstall` queda para cuando el entorno se rompe o se cambia de sistema sobre la misma carpeta. Si `make dev` estaba corriendo, reiniciarlo después: sigue usando el `.venv` viejo hasta que se corta.

## Correr la aplicación

```bash
uvicorn app.main:app --reload
```

| URL | Qué es |
|---|---|
| http://localhost:8000 | La API |
| http://localhost:8000/docs | Documentación interactiva (Swagger), para probar los endpoints a mano |
| http://localhost:8000/redoc | Documentación alternativa |

La opción `--reload` reinicia el servidor solo cada vez que se guarda un archivo. Se usa únicamente en desarrollo.

Para detenerlo: `Ctrl+C`.

## Correr los tests

```bash
pytest
```

Con más detalle por test:

```bash
pytest -v
```

Con reporte de cobertura, indicando qué líneas no cubre ningún test:

```bash
pytest --cov=app --cov-report=term-missing
```

Un solo archivo o un solo test:

```bash
pytest tests/test_auth.py
pytest tests/test_auth.py::test_register_con_email_duplicado
```

Para probar el estado del partido sin el motor de simulación:

```bash
python -m pytest tests/test_match_state.py -q
```

Estas pruebas usan un mock del motor con estados controlados y una base SQLite
temporal. Cubren publicación y consulta del estado, acceso, concurrencia,
movimiento mediante un comportamiento y la secuencia inicio, gol, pausa,
reanudación y fin del partido.


## Ver un partido de prueba en el navegador

Sin creación/inicio de partidos ni motor, el script genera dos usuarios, dos
clubes, seis jugadores por club (tres en cancha), una sala y un partido iniciado.
Publica estados mediante el mismo servicio que usa la API. Los movimientos y
goles son simulados; no ejecuta los comportamientos de los jugadores.

Usar dos terminales. Detener primero el backend anterior si ocupa el puerto 8000.
El script levanta su propia API en el mismo proceso que la simulación.

1. Frontend, desde `futbot-frontend`:

   ```bash
   npm run dev
   ```

2. Demo y backend, desde `futbot-backend`, con el entorno virtual activado:
esta demo levanta su propio backend para pruebas
   ```bash
   python -m scripts.demo_match
   ```



El script usa `DATABASE_URL` del `.env` (por defecto `futbot.db`). Ejecutarlo
desde `futbot-backend`. No iniciar otro uvicorn para esta demo.
No borra datos: cada ejecución agrega cuentas y un partido nuevos.

La terminal imprime los dos emails, la contraseña `FutbotDemo123!`, el ID y la
URL del partido. Iniciar sesión en `http://localhost:5173/login` con uno de esos
emails y abrir la URL `/partidos/<ID>` indicada (o ingresar el ID en Home).
Después, presionar **Enter en la terminal de la demo** para comenzar.

Durante dos minutos publica una actualización por segundo: movimientos,
posesión, reloj, gol local a los 40 segundos, gol visitante a los 80 y resultado
final 1–1. Los dos goles quedan registrados en `goals`. La cancha usa la escala provisional 100 × 60, con origen en el centro.
Para probar ambos usuarios, usar otro perfil o una ventana de incógnito.

Opciones:

```bash
python -m scripts.demo_match --static           # Solo estado inicial, sin animación
python -m scripts.demo_match --duration 60      # Demo de un minuto
python -m scripts.demo_match --no-wait          # Animación inmediata, sin Enter
python -m scripts.demo_match --frontend-url http://localhost:5174
python -m scripts.demo_match --port 8001        # También cambiar las URLs del frontend
```

`Ctrl+C` detiene la demo y su backend. Los goles, marcador persistido y datos
de los clubes se conservan; las posiciones y el reloj en memoria se pierden.
Al finalizar o con `--static`, la API permanece abierta hasta `Ctrl+C`. Para
volver a empezar, ejecutar el comando y usar las nuevas credenciales y URL.
Si la sesión vence durante una demo larga, volver a iniciar sesión y abrir la URL.
El frontend debe apuntar al backend mediante `VITE_API_URL` y su origen debe
estar incluido en `CORS_ORIGINS`.

## Estado del partido por WebSocket

El frontend mantiene una conexión a `/api/matches/{match_id}/ws`; no consulta
periódicamente el endpoint HTTP de estado. Configurar `VITE_WS_URL` en el
frontend (por ejemplo `ws://localhost:8000`, o `wss://` si se usa HTTPS).
Si no se configura, deriva esa URL de `VITE_API_URL`.

El primer mensaje del cliente es `{"type":"auth","token":"<access_token>"}`.
El servidor valida la sesión y la pertenencia a uno de los clubes antes de
enviar datos. El token no se envía en la URL. El origen del navegador debe
estar permitido en `CORS_ORIGINS`.

Mensajes del servidor:

- `{"type":"state","state":{...}}`: snapshot completo, con `match_id` y
  `revision`. Se envía el último al conectar y los nuevos al publicarse.
- `{"type":"error","status":409,"message":"..."}`: todavía no hay estado;
  la conexión permanece abierta hasta la primera publicación.
- Otros errores: `401` (sesión), `403` (acceso), `404` (partido), `422` (ID).
  Estos cierran la conexión y no provocan reintentos del frontend.
- `{"type":"ping"}` cada 15 segundos; el cliente responde
  `{"type":"pong"}`. Es mantenimiento de conexión, no consulta de estado.
- `{"type":"SUBSTITUTION_SCHEDULED","ok":true,"status":"scheduled",...}`:
  sustitución aceptada durante el juego; queda pendiente hasta la siguiente
  pausa. `{"type":"SUBSTITUTION_APPLIED","ok":true,"status":"applied",...}`
  confirma que el cambio ya se aplicó.
- `{"type":"SUBSTITUTION_STATE","pendingSubstitution":...,"changesUsedThisPause":0}`:
  estado privado del club autenticado al conectar o reconectar. No se incluye
  en los snapshots compartidos con ambos clubes.

El cliente puede solicitar un cambio enviando
`{"type":"SUBSTITUTE_PLAYER","outPlayerId":"<id titular>","inPlayerId":"<id suplente>"}`.
El servidor determina el club a partir de la sesión autenticada (no acepta un
`club_id` del cliente). Los identificadores deben pertenecer al partido; el que
sale debe estar en cancha y el que entra debe ser suplente de ese mismo club.
Durante el juego se acepta como máximo una solicitud pendiente por club y se
aplica en la próxima pausa; si ya no quedan pausas, se rechaza. Durante una
pausa se aplica inmediatamente y se permite como máximo un cambio por club en
esa pausa. Los rechazos se devuelven solo al socket que hizo la solicitud como
`{"type":"error","ok":false,"error_code":"SUBSTITUTION_LIMIT_REACHED","message":"..."}`.
El cliente debe tomar decisiones por `error_code`, no por el texto del mensaje.
Los eventos programados y aplicados se envían a todos los sockets autorizados de
ese partido.

En las ligas configuradas sin empates, si el tiempo regular termina igualado,
el motor inicia automáticamente una tanda de penales: hasta cinco intentos por
club, alternados, con un máximo de 10 segundos de juego por intento. Se emiten
`PENALTIES_STARTED`, `PENALTY_SHOT_RESULT` y `PENALTIES_FINISHED` con el marcador
parcial/final. `PENALTIES_STARTED` informa además `maxSecondsPerAttempt` y
`tickRate` para sincronizar el reloj visual del cliente con los ticks del motor.
Si la tanda termina igualada, `PENALTIES_TIEBREAK` anuncia el
ganador elegido al azar. El ganador queda guardado en
`matches.penalty_winner_club_id` junto con la publicación del estado final.
Durante los penales, el snapshot conserva `status: "paused"` e incluye
`phase: "penalties"` y `penalty` con `shooter_id`, `goalkeeper_id`, el marcador
y los intentos de la tanda, `seconds_remaining` y, al finalizar,
`winner_club_id`.
Los eventos generados en el tick final se entregan antes del cierre normal del
WebSocket.

El motor mantiene titulares y suplentes en memoria mientras corre el partido.
Esta operación no modifica la convocatoria original en la base de datos; los
snapshots reflejan qué jugadores están en cancha en cada tick.

El último snapshot se guarda en `app/engine/live_state.py`, en un diccionario
por `match_id`. `publish_match_state` valida el tick, actualiza ese diccionario y
llama a `manager.broadcast` (`app/ws/manager.py`). Cada socket tiene una cola
acotada: un cliente lento recibe el último snapshot sin bloquear al motor. No
hay tabla de snapshots ni observadores de archivos. No se hace flush ni commit
para publicar posiciones, posesión o reloj.

Motor y servidor deben vivir en el **mismo proceso, con un solo worker**.
Los hilos sí comparten el estado. Para varios procesos o máquinas hará falta un
broker compartido; un diccionario local no se comparte entre workers. Al reiniciar
se pierde el estado en vivo y el motor debe volver a publicar un estado inicial.
No se recuperan posiciones históricas desde la base. Si una base anterior conserva
la tabla `match_states`, queda sin uso; no se elimina automáticamente.

La entrada recomendada para el motor es `publish_engine_tick` (o
`publish_engine_state` con un objeto que implemente `capture_state`). Usar una
sesión limpia y confirmar la creación del partido antes de publicar. Esta capa:

- Valida que cada incremento del marcador tenga sus eventos `goal` con club.
- Persiste una fila `Goal` por gol, con club, autor y segundo; actualiza el
  marcador y los goles del jugador. Un gol en contra se guarda sin autor.
- Hace commit solo ante goles o cambios de estado (pausa, reanudación, fin).
- Al terminar, registra el final y libera a los jugadores; cierra la sala amistosa.
- Publica después del commit de esos eventos. Si falla, revierte SQL y conserva
  la revisión anterior en memoria. Los reintentos con revisión antigua se rechazan.

No agregar un `db.commit()` después de cada tick del motor. La función de bajo
nivel `publish_match_state` solo publica; no crea goles ni confirma transacciones.
El motor debe emitir los eventos de gol, no deducir autores a partir del marcador.
La demo pasa por la capa del motor y sirve de ejemplo de integración.

## Tabla de posiciones en vivo

El endpoint `GET /api/leagues/{league_id}/standings` devuelve la tabla actual.
Para recibir actualizaciones sin polling, conectar a
`/api/leagues/{league_id}/standings/ws` y enviar primero
`{"type":"auth","token":"<access_token>"}`. El servidor responde con
`{"type":"standings","league_id":"...","standings":[...]}` y envía
`standings_updated` con la tabla recalculada cada vez que termina un partido de
esa liga.

Ante una desconexión, la pantalla conserva el último snapshot con una advertencia
y reconecta con espera progresiva de 1 a 10 segundos. Al reconectar recibe el
estado vigente y descarta revisiones anteriores. Al finalizar, cierra el socket.
La sesión se comprueba al conectar y en el heartbeat, sin consultar snapshots.
El logout notifica al manager para cerrar la conexión de inmediato; el vencimiento
del token también la cierra aunque no se publique ningún estado.

Para probar el stream y sus permisos: `python -m pytest tests/test_match_websocket.py -q`.

## Base de datos

En desarrollo se usa SQLite: la base es un único archivo (`futbot.db`) que se crea solo al levantar la aplicación por primera vez. No requiere instalación ni servidor.

El archivo está en el `.gitignore`: cada integrante tiene su propia copia local.

Para empezar de cero, alcanza con borrarlo:

```bash
rm futbot.db
```

Al volver a levantar la aplicación se recrean las tablas y se cargan los comportamientos por defecto.



## Problemas frecuentes

**`ModuleNotFoundError` al correr uvicorn o pytest**
El entorno virtual no está activo. El prompt tiene que mostrar `(.venv)`.

**El frontend recibe errores de CORS**
Verificar que `CORS_ORIGINS` en el `.env` incluya la URL exacta del frontend, con protocolo y puerto (`http://localhost:5173`).

**El puerto 8000 está ocupado**

```bash
uvicorn app.main:app --reload --port 8001
```

Si se cambia el puerto, hay que actualizar `VITE_API_URL` y `VITE_WS_URL` en el frontend.


## Verificación de correo

El registro conserva la respuesta 201 y crea una cuenta con `email_verified_at = null`.
La cuenta y el hash del token se confirman antes del envío SMTP. Si el envío falla,
la cuenta permanece creada y puede solicitar un nuevo enlace. El token dura 24 horas
por defecto, solo se guarda su SHA-256 y nunca se incluye en la respuesta del registro.

- `POST /api/auth/verify-email`, body `{"token": "..."}`: devuelve 200 al verificar.
  Repetir un token ya consumido devuelve 200 sin cambiar la fecha, incluso después
  de su vencimiento. Un token vencido devuelve 400 / `EMAIL_VERIFICATION_TOKEN_EXPIRED`;
  uno desconocido o invalidado devuelve 400 / `EMAIL_VERIFICATION_TOKEN_INVALID`.
- `POST /api/auth/resend-verification`, body `{"email": "usuario@example.com"}`:
  devuelve siempre 200 con un mensaje genérico para emails válidos, aunque no existan,
  estén verificados o se haya alcanzado el límite. Cada reenvío invalida enlaces pendientes.
  Por defecto permite un reenvío por minuto por email y diez solicitudes por hora por IP.
  Los contadores se guardan en la base y se comparten entre workers; los emails e IPs
  se usan como hashes en sus claves. Las ventanas vencidas se reutilizan al recibir otra solicitud.
- Login y refresh rechazan cuentas sin verificar con 403 / `EMAIL_NOT_VERIFIED`.
  Las credenciales incorrectas siguen devolviendo 401.

Configurar las variables SMTP y `EMAIL_VERIFICATION_URL` de `.env.example` antes de
usar correo real. El proveedor implementa `EmailSender`; los tests sustituyen la
dependencia `get_email_sender` por un fake, sin conexiones SMTP. No se envían emails
reales al ejecutar las pruebas. El enlace apunta a una página del frontend que debe
leer el token y llamar al endpoint POST; esta implementación agrega únicamente el backend.
En producción usar HTTPS y configurar correctamente las IPs de proxy confiables en
Uvicorn: el límite usa `request.client.host`, sin interpretar directamente encabezados enviados por el cliente.

Al arrancar se agrega la columna faltante a `users` y se crean las tablas nuevas,
sin borrar datos. Las cuentas anteriores quedan sin verificar y deben solicitar
reenvío antes de su próximo login o refresh. Las sesiones de acceso ya emitidas
conservan su vigencia. Para actualizar una base existente, realizar el primer arranque
con un solo proceso antes de levantar los demás workers (la migración aditiva no
coordina ejecuciones simultáneas). No hace falta borrar `futbot.db`.

## Recuperación de contraseña

- `POST /api/auth/forgot-password`, body `{"email": "usuario@example.com"}`:
  responde HTTP 200 con `{"detail": "Si corresponde, recibirás un correo para recuperar tu contraseña."}`
  tanto para cuentas existentes como inexistentes, solicitudes limitadas y fallos de envío.
  Un email con formato inválido devuelve 422. El envío se procesa con `BackgroundTasks`
  después de responder, para que la demora SMTP no revele la existencia de la cuenta.
  La tarea usa una sesión propia de base de datos; no es una cola persistente: si el
  proceso termina antes de completarla, el usuario debe solicitar otro enlace.
- `POST /api/auth/reset-password`, body `{"token": "...", "newPassword": "..."}`:
  acepta contraseñas de 8 a 20 caracteres, igual que el registro. Devuelve 200 al
  actualizar la contraseña con bcrypt y consumir el token en una misma transacción.
  No inicia sesión automáticamente ni verifica el correo de una cuenta pendiente.
- Un token desconocido, manipulado, reemplazado o ya usado devuelve 400 con
  `PASSWORD_RESET_TOKEN_INVALID`. Uno vencido sin consumir devuelve 400 con
  `PASSWORD_RESET_TOKEN_EXPIRED` y queda consumido; los siguientes intentos son inválidos.
  Los tokens reemplazados también se marcan consumidos al presentarlos. Un token
  desconocido no tiene un registro que se pueda consumir y no afecta enlaces legítimos.
- Cada nuevo enlace invalida los anteriores pendientes. Los tokens se generan con
  `secrets.token_urlsafe(48)` y solo se persiste su SHA-256. No se devuelven al solicitar
  recuperación ni se registran en logs. Los tokens de verificación de correo y de
  recuperación se almacenan por separado y no son intercambiables.
- Por defecto el enlace dura 30 minutos. `PASSWORD_RESET_URL` apunta a la página
  del frontend que recibirá `?token=...` y enviará el POST con la nueva contraseña.
  El valor local es `http://localhost:5173/reset-password`; esta entrega implementa
  únicamente el backend, por lo que esa pantalla debe agregarse en el frontend.
- `PASSWORD_RESET_INTERVAL_SECONDS` limita las solicitudes por email (60 segundos),
  `PASSWORD_RESET_IP_LIMIT` las solicitudes por IP (10) y
  `PASSWORD_RESET_IP_WINDOW_SECONDS` la ventana por IP (3600 segundos).
  Se reutiliza la tabla de contadores con ámbitos `reset-email` y `reset-ip`,
  independientes de los límites de verificación. Las claves guardan hashes, y las
  solicitudes de cuentas inexistentes también cuentan para los límites.
- Al cambiar la contraseña se revocan las sesiones existentes del usuario: los tokens
  de acceso y refresh dejan de autorizar nuevas solicitudes. Se notifica el cierre
  a las suscripciones de partidos del proceso mediante el gestor WebSocket existente.
- Se reutiliza la configuración SMTP actual y se agrega `EmailSender.send_password_reset`.
  Los tests usan un emisor simulado y no envían correos. Los errores de envío se registran
  únicamente con su tipo y códigos SMTP, sin contraseñas, destinatarios ni enlaces.

Al arrancar se crea `password_reset_tokens` mediante la inicialización habitual;
no se necesita borrar la base ni modificar columnas de usuarios. Configurar la URL
pública con HTTPS y reiniciar el backend después de cambiar variables de entorno.

## Puntos del ranking global

Al terminar todos los partidos de una liga pública, cada club recibe 3 puntos
por victoria y 1 por empate, calculados a partir de los marcadores finales.
Se suman al ranking previo del club. Las ligas privadas y los amistosos no suman.
La acreditación y el cierre se guardan en una misma transacción y la marca
`rooms.ranking_settled` impide volver a acreditar una liga ante reintentos.

Al reiniciar el backend se agrega esa columna automáticamente a las bases
existentes y se recuperan las ligas pendientes de acreditación cuyos partidos
ya terminaron, incluidas las ligas históricas. No hay que borrar la base.
Los puntos ya existentes se conservan; esta recuperación presupone que las
ligas históricas no fueron acreditadas manualmente por fuera de la aplicación.
