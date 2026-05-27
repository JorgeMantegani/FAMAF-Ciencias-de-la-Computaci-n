#!/usr/bin/env bash
# Ejecuta el cliente HFTP hacia una dirección .onion usando torsocks.
# Uso: ./scripts/tor/run_client_tor.sh <direccion.onion> [puerto]
# Ejemplo: ./scripts/tor/run_client_tor.sh abc123xyz456.onion

if [[ $# -lt 1 ]]; then
   echo "Uso: $0 <direccion.onion> [puerto]" >&2
   echo "Ejemplo: $0 abc123xyz456.onion 19500" >&2
   exit 1
fi

ONION="$1"
PORT="${2:-19500}"

if ! command -v torsocks &>/dev/null; then
   echo "torsocks no está instalado. Instálalo con: sudo apt install torsocks" >&2
   exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -f "$REPO_ROOT/solucion/client.py" ]]; then
   CLIENT_DIR="$REPO_ROOT/solucion"
elif [[ -f "$REPO_ROOT/output/kickstart_lab2/client.py" ]]; then
   CLIENT_DIR="$REPO_ROOT/output/kickstart_lab2"
elif [[ -f "$REPO_ROOT/client.py" ]]; then
   CLIENT_DIR="$REPO_ROOT"
else
   echo "No se encontró client.py." >&2
   exit 1
fi

cd "$CLIENT_DIR"
exec torsocks python client.py "$ONION" -p "$PORT"
