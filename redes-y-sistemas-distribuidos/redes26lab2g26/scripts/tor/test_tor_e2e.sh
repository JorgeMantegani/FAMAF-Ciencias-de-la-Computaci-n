#!/usr/bin/env bash
# Prueba de extremo a extremo: servidor HFTP como .onion + cliente vía torsocks.
# Requiere: Tor en marcha, configuración HFTP en torrc (ej. sudo ./setup_tor_hftp.sh).
# Uso: ./scripts/tor/test_tor_e2e.sh
# Opcional: sudo para leer la dirección .onion; si no, se usa ONION env o se pide.

set -e
HOSTNAME_FILE="/var/lib/tor/hftp_service/hostname"
PORT=19500
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [[ -f "$REPO_ROOT/solucion/server.py" ]]; then
   SERVER_DIR="$REPO_ROOT/solucion"
elif [[ -f "$REPO_ROOT/output/kickstart_lab2/server.py" ]]; then
   SERVER_DIR="$REPO_ROOT/output/kickstart_lab2"
elif [[ -f "$REPO_ROOT/server.py" ]]; then
   SERVER_DIR="$REPO_ROOT"
else
   echo "No se encontró server.py en solucion/, output/kickstart_lab2/ ni en la raíz del proyecto." >&2
   exit 1
fi
DATADIR="$SERVER_DIR/testdata"
PIDFILE=""

DOWNLOAD_DIR=""
cleanup() {
   if [[ -n "$PIDFILE" ]] && [[ -f "$PIDFILE" ]]; then
      pid=$(cat "$PIDFILE")
      kill "$pid" 2>/dev/null || true
      rm -f "$PIDFILE"
   fi
   [[ -n "$DOWNLOAD_DIR" ]] && rm -rf "$DOWNLOAD_DIR"
}
trap cleanup EXIT

mkdir -p "$DATADIR"
echo "contenido de prueba" > "$DATADIR/archivo.txt"

# Obtener dirección .onion
ONION="${ONION:-}"
if [[ -z "$ONION" ]] && [[ -f "$HOSTNAME_FILE" ]]; then
   ONION=$(cat "$HOSTNAME_FILE" 2>/dev/null) || true
fi
if [[ -z "$ONION" ]]; then
   ONION=$(sudo cat "$HOSTNAME_FILE" 2>/dev/null) || true
fi
if [[ -z "$ONION" ]]; then
   echo "No se pudo leer la dirección .onion desde $HOSTNAME_FILE." >&2
   echo "Ejecuta: sudo ./scripts/tor/setup_tor_hftp.sh" >&2
   echo "O exporta ONION=tu_direccion.onion y vuelve a ejecutar este script." >&2
   exit 1
fi
echo "Usando dirección .onion: $ONION"

# Arrancar servidor
python3 "$SERVER_DIR/server.py" -a 127.0.0.1 -p "$PORT" -d "$DATADIR" &
pid=$!
PIDFILE=$(mktemp)
echo $pid > "$PIDFILE"
sleep 1.5
if ! kill -0 $pid 2>/dev/null; then
   echo "El servidor no arrancó." >&2
   exit 1
fi
echo "Servidor HFTP en marcha (PID $pid)."

# Cliente vía torsocks (ejecutar desde un dir de descarga para no pisar testdata)
DOWNLOAD_DIR=$(mktemp -d)
cd "$DOWNLOAD_DIR"
echo "Conectando cliente vía torsocks a $ONION:$PORT..."
if ! echo "archivo.txt" | torsocks python3 "$SERVER_DIR/client.py" "$ONION" -p "$PORT"; then
   echo "--- El cliente falló. Comprueba que Tor esté activo (systemctl status tor@default)." >&2
   exit 1
fi
if [[ ! -f archivo.txt ]]; then
   echo "--- Error: no se creó el archivo descargado archivo.txt" >&2
   exit 1
fi
EXPECTED="contenido de prueba"
if [[ "$(cat archivo.txt)" != "$EXPECTED" ]]; then
   echo "--- Error: el contenido descargado no coincide. Esperado: '$EXPECTED'" >&2
   exit 1
fi
echo "--- Prueba completada: listado, descarga y contenido correcto vía Tor."
