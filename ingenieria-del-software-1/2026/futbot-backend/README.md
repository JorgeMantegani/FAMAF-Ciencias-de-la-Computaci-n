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
