#!/usr/bin/env bash
# Muestra la dirección .onion del servicio HFTP.
# Requiere permisos de lectura en /var/lib/tor/hftp_service/hostname
# (normalmente: sudo ./scripts/tor/get_onion_hostname.sh)

HOSTNAME_FILE="/var/lib/tor/hftp_service/hostname"

if [[ -f "$HOSTNAME_FILE" ]]; then
   cat "$HOSTNAME_FILE"
else
   echo "No se encontró $HOSTNAME_FILE. ¿Tor está configurado y corriendo? ¿Ejecutaste setup_tor_hftp.sh?" >&2
   exit 1
fi
