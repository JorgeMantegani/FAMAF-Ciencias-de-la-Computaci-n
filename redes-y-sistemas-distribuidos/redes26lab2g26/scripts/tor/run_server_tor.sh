#!/usr/bin/env bash
# Arranca el servidor HFTP escuchando en 127.0.0.1:19500 para usarlo con Tor.
# Uso: ./scripts/tor/run_server_tor.sh [directorio_datos]
# Ejemplo: ./scripts/tor/run_server_tor.sh testdata

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATADIR="${1:-testdata}"
PORT=19500

# Buscar server.py: solucion/ o directorio actual
if [[ -f "$REPO_ROOT/solucion/server.py" ]]; then
   SERVER_DIR="$REPO_ROOT/solucion"
elif [[ -f "$REPO_ROOT/output/kickstart_lab2/server.py" ]]; then
   SERVER_DIR="$REPO_ROOT/output/kickstart_lab2"
elif [[ -f "$REPO_ROOT/server.py" ]]; then
   SERVER_DIR="$REPO_ROOT"
else
   echo "No se encontró server.py en solucion/, output/kickstart_lab2/ ni en la raíz del repo." >&2
   exit 1
fi

cd "$SERVER_DIR"
# Directorio de datos: si es relativo, es respecto al directorio del servidor
if [[ "$DATADIR" != /* ]]; then
   DATADIR="$SERVER_DIR/$DATADIR"
fi
if [[ ! -d "$DATADIR" ]]; then
   echo "El directorio de datos no existe: $DATADIR" >&2
   exit 1
fi

exec python3 server.py -a 127.0.0.1 -p "$PORT" -d "$DATADIR"