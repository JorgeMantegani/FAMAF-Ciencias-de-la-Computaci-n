# FutBot — Frontend

Interfaz web del juego FutBot: registro de clubes, creación de jugadores y comportamientos, ligas, amistosos y visualización del partido en vivo en 2D.

Este repositorio maneja únicamente la interacción con el usuario. Toda la lógica de negocio y los datos viven en [futbot-backend](https://github.com/IngSoft1-los-transistores/futbot-backend).

**Materia:** Ingeniería de Software I· **Equipo:** Los Transistores

> ⚠️ **Esta aplicación no funciona sola: necesita el backend corriendo.** Antes de levantar el frontend, seguir las instrucciones de instalación del repositorio [futbot-backend](https://github.com/IngSoft1-los-transistores/futbot-backend).


## Stack

| Componente | Tecnología |
|---|---|
| Librería | React 19 |
| Build y dev server | Vite |
| Lenguaje | JavaScript |
| Ruteo | React Router |
| HTTP | axios |
| Tiempo real | WebSocket nativo del navegador |
| Linter | ESLint |

## Requisitos previos

- **Node.js 22 LTS o superior** — verificar con `node --version`
- **npm** (viene con Node) — verificar con `npm --version`
- **El backend corriendo** en `http://localhost:8000`

## Instalación

**1. Clonar el repositorio**

```bash
git clone https://github.com/IngSoft1-los-transistores/futbot-frontend.git
cd futbot-frontend
```

**2. Instalar las dependencias**

```bash
npm install
```

Esto crea la carpeta `node_modules/`, que no se sube al repositorio.

**3. Configurar las variables de entorno**

```bash
cp .env.example .env
```

Los valores por defecto funcionan si el backend corre en el puerto 8000. Si se cambió el puerto del backend, hay que actualizar las dos variables.

## Correr la aplicación

Con el backend ya levantado, en otra terminal:

```bash
npm run dev
```

La aplicación queda en **http://localhost:5173**.

Para detenerla: `Ctrl+C`.

### Otros comandos

| Comando | Qué hace |
|---|---|
| `npm run dev` | Servidor de desarrollo, con recarga automática al guardar |
| `npm run build` | Compila la versión de producción en `dist/` |
| `npm run preview` | Sirve lo compilado, para verificar el build |
| `npm run lint` | Revisa el código con ESLint |

## Comandos rápidos con make

El `Makefile` de la raíz agrupa los comandos de uso diario. El backend tiene el suyo, con los mismos nombres.

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
| `make install` | Instala las dependencias y el Chromium que usa Playwright |
| `make reinstall` | Borra `node_modules` e instala todo de cero |
| `make dev` | Levanta la app en http://localhost:5173 |
| `make test` | Corre los tests unitarios y, si pasan, los e2e |
| `make test-unit` | Corre sólo los tests unitarios (Vitest), una vez |
| `make test-e2e` | Corre sólo los tests e2e (Playwright) |
| `make coverage` | Corre las dos coberturas y calcula el total combinado |
| `make coverage-unit` | Cobertura de los tests unitarios (Vitest), en `coverage/index.html` |
| `make coverage-e2e` | Cobertura de los tests e2e (Playwright), en `coverage-e2e/index.html` |
| `make lint` | Revisa el código con ESLint |
| `make clean` | Borra `dist/`, los tres reportes de cobertura y los de Playwright. No toca `.env` ni `node_modules` |

`make test` devuelve código de salida distinto de 0 si algún test falla, así que sirve para CI.

**Cómo leer la cobertura.** `make coverage` muestra tres tablas: la de los unitarios, la de los e2e y el **total** (`coverage-total/index.html`). El total no es la suma de las otras dos: muchas líneas las recorren ambas suites, así que se cuenta la unión, línea por línea. Por eso el total sólo informa **líneas**: sentencias, ramas y funciones las divide distinto cada herramienta y no se pueden combinar sin contar de más.

La cobertura de los e2e se mide con Chromium sólo cuando se corre `make coverage-e2e` (o `make coverage`); `make test-e2e` no mide nada y no se vuelve más lento. El primer test de `tests/persistence.spec.js` abre su propio navegador para simular que se cierra y se vuelve a abrir, y queda fuera de la medición.

Los tests e2e **no necesitan el backend**: simulan la API, y Playwright levanta su propio servidor de Vite en el puerto 5173. Por eso fallan si `make dev` ya está corriendo: hay que cortarlo antes. En Linux o WSL, si Chromium no arranca por librerías faltantes, correr una vez `sudo npx playwright install-deps`.

**Windows y WSL:** `node_modules` trae binarios propios de cada sistema, así que uno instalado desde Windows no funciona en WSL ni al revés. Si se usa WSL, clonar el repo dentro de WSL (por ejemplo en `~/`), no trabajar sobre `/mnt/c/...`: además de evitar el problema, es mucho más rápido. `make reinstall` queda para cuando el entorno se rompe o se cambia de sistema sobre la misma carpeta.

## Variables de entorno

| Variable | Para qué | Valor en desarrollo |
|---|---|---|
| `VITE_API_URL` | URL base de la API REST | `http://localhost:8000` |
| `VITE_WS_URL` | URL base de los WebSockets | `ws://localhost:8000` |

El prefijo `VITE_` es obligatorio: Vite sólo expone al navegador las variables que lo llevan.

El archivo `.env` no se sube al repositorio. Se usa `.env.example` como plantilla.



## Comunicación con el backend

| Canal | Para qué |
|---|---|
| **HTTP** | Autenticación, plantel, comportamientos, ligas y amistosos |
| **WebSocket** | Partido en vivo, lobby de liga y sala de amistoso |


## Problemas frecuentes

**Errores de CORS en la consola del navegador**
El backend no está autorizando este origen. Verificar que `CORS_ORIGINS` en el `.env` del backend incluya `http://localhost:5173`.

Antes de tocar el `.env` del backend, **mirar en qué puerto arrancó Vite**: si el 5173 está ocupado (por ejemplo por otra instancia que quedó abierta), Vite salta al 5174 sin más aviso que su propia línea `Local:`. El backend sólo autoriza el 5173, así que todas las peticiones fallan con un error de CORS que parece un problema del backend y no lo es. La solución es cerrar la instancia vieja y levantar de nuevo en el 5173, no agregar el 5174 a `CORS_ORIGINS`.

**`Failed to fetch` o `ERR_CONNECTION_REFUSED`**
El backend no está corriendo, o `VITE_API_URL` apunta al puerto equivocado.

**Cambié el `.env` y no toma los valores nuevos**
Vite lee las variables de entorno al arrancar. Hay que reiniciar `npm run dev`.

**El WebSocket se cierra apenas se conecta**
El token es inválido o falta. El navegador no permite enviar el header `Authorization` en un WebSocket, por eso el token viaja como query param (`?token=...`).

**El puerto 5173 está ocupado**

```bash
npm run dev -- --port 5174
```

Si se cambia el puerto, hay que agregar el nuevo origen a `CORS_ORIGINS` en el backend.

### Pruebas de interfaz

```bash
### requiere node.js 22 o mayor para instalar playwright.
node -v

# instalacion de playwright
npx playwright install chromium

### en caso de tener una version menor que 22

sudo apt remove nodejs
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

### correr el test

npm run test:e2e
```









## Estado actual del partido

La sala amistosa abre `/partidos/:match_id` al iniciar o elegir “Ir al partido”.
Esta ruta muestra la cancha completa, el marcador y las actualizaciones por
WebSocket. `/matches/:match_id` sigue disponible para enlaces anteriores y la
demo. Desde Home también se puede ingresar el ID manualmente.

La conexión usa `/api/matches/{match_id}/ws`, con el token de sesión en el primer
mensaje. `VITE_WS_URL` configura la dirección; si no existe, se deriva de
`VITE_API_URL`. No se consulta periódicamente el estado por HTTP. Ante una
interrupción, conserva el último estado, avisa y reconecta; ignora revisiones
anteriores y cierra la conexión al finalizar el partido.

La cabecera muestra los clubes participantes. No se presupone el formato del
partido, ya que el snapshot actual no incluye ese dato. La cancha usa dimensiones
provisionales de 100 × 60 con origen en el centro.

Los nombres de los comportamientos se obtienen del catálogo (`/api/behaviors`)
y de los datos de la sala al navegar. Si el snapshot incluye `behavior_name`,
se prioriza ese valor. Un comportamiento privado del rival puede no estar en el
catálogo: si no hay nombre disponible se muestra “Nombre no disponible”, sin
exponer el UUID como etiqueta. Un fallo del catálogo no interrumpe el partido.

Las acciones corresponden al último snapshot recibido, no a un historial completo.

