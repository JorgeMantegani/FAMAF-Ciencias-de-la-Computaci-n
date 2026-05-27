#!/usr/bin/env bash
# Configura Tor para exponer el servidor HFTP como onion service.
# Uso: sudo ./scripts/tor/setup_tor_hftp.sh
# Requiere: tor instalado (apt install tor).

set -e

TORRC="/etc/tor/torrc"
MARKER="# HFTP onion service (Lab2)"
HIDDEN_DIR="/var/lib/tor/hftp_service"
HIDDEN_PORT="HiddenServicePort 19500 127.0.0.1:19500"

if [[ $EUID -ne 0 ]]; then
   echo "Este script debe ejecutarse con sudo (para escribir en /etc/tor/torrc y reiniciar tor)." >&2
   exit 1
fi

if ! command -v tor &>/dev/null; then
   echo "Tor no está instalado. Instálalo con: sudo apt install tor" >&2
   exit 1
fi

# Crear directorio del servicio y dar ownership al usuario con el que corre Tor
mkdir -p "$HIDDEN_DIR"
TOR_USER=""
if ps -o user= -C tor 2>/dev/null | head -1 | grep -q .; then
   TOR_USER=$(ps -o user= -C tor 2>/dev/null | head -1 | tr -d ' ')
fi
if [[ -z "$TOR_USER" ]]; then
   for u in debian-tor tor; do
      if getent passwd "$u" &>/dev/null; then
         TOR_USER="$u"
         break
      fi
   done
fi
if [[ -n "$TOR_USER" ]]; then
   chown "$TOR_USER:$TOR_USER" "$HIDDEN_DIR"
   chmod 700 "$HIDDEN_DIR"
   echo "Directorio $HIDDEN_DIR creado/actualizado, propietario: $TOR_USER, permisos 700"
else
   echo "Advertencia: no se pudo detectar el usuario de Tor; el directorio puede tener permisos incorrectos." >&2
fi

# Comprobar si ya está la configuración (con o sin / al final)
if grep -q "HiddenServiceDir.*hftp_service" "$TORRC" 2>/dev/null; then
   echo "La configuración del servicio HFTP ya está en $TORRC."
else
   echo "Añadiendo configuración del onion service a $TORRC..."
   {
     echo ""
     echo "$MARKER"
     echo "HiddenServiceDir $HIDDEN_DIR/"
     echo "$HIDDEN_PORT"
   } >> "$TORRC"
   echo "Configuración añadida."
fi

# Verificar que la configuración sea válida (evita fallos silenciosos)
echo "Verificando configuración de Tor..."
DEFAULTS="/usr/share/tor/tor-service-defaults-torrc"
VERIFY_CMD="tor -f $TORRC --verify-config"
[[ -f "$DEFAULTS" ]] && VERIFY_CMD="tor --defaults-torrc $DEFAULTS -f $TORRC --verify-config"
if ! $VERIFY_CMD 2>&1; then
   echo "Error: la configuración en $TORRC no es válida. Revisa los mensajes anteriores." >&2
   echo "Sugerencia: busca líneas duplicadas (HiddenServiceDir/HiddenServicePort) en $TORRC" >&2
   exit 1
fi
# En Debian/Ubuntu la instancia que usa /etc/tor/torrc es tor@default, no tor
echo "Reiniciando Tor..."
if systemctl list-unit-files 2>/dev/null | grep -q 'tor@default'; then
   systemctl restart tor@default
   TOR_UNIT="tor@default"
else
   systemctl restart tor
   TOR_UNIT="tor"
fi

if ! systemctl is-active --quiet "$TOR_UNIT"; then
   echo "Error: $TOR_UNIT no está activo. Revisa: sudo journalctl -u $TOR_UNIT -n 30" >&2
   exit 1
fi
echo "Servicio activo: $TOR_UNIT"

echo "Tor está activo. Esperando a que se genere el hostname..."
for i in {1..10}; do
   if [[ -f "$HIDDEN_DIR/hostname" ]]; then
     echo "Dirección .onion:"
     cat "$HIDDEN_DIR/hostname"
     exit 0
   fi
   sleep 1
done

echo "Tor está corriendo pero el hostname aún no aparece." >&2
echo "Comprueba permisos: ls -la $HIDDEN_DIR (debe ser propietario el usuario de Tor)" >&2
echo "Logs de Tor: sudo journalctl -u tor -n 50 --no-pager" >&2
exit 1
