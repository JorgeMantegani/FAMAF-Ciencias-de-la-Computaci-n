#!/usr/bin/env python
# encoding: utf-8
# Revisión 2019 (a Python 3 y base64): Pablo Ventura
# Revisiones 2013-2014 Carlos Bederián
# Revisión 2011 Nicolás Wolovick
# Copyright 2008-2010 Natalia Bidart y Daniel Moisset
# $Id: client.py 387 2011-03-22 13:48:44Z nicolasw $

import argparse
import logging
import socket
import sys
import time
from base64 import b64decode

from constants import (
    CODE_OK,
    CONTENT_LENGTH_PREFIX,
    DEFAULT_ADDR,
    DEFAULT_PORT,
    EOL,
    FILE_NOT_FOUND,
)

_CRLF = b"\r\n"


class Client:

    def __init__(self, server: str = DEFAULT_ADDR, port: int = DEFAULT_PORT) -> None:
        """
        Nuevo cliente, conectado al `server' solicitado en el `port' TCP
        indicado.

        Si falla la conexión, genera una excepción de socket.
        """
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((server, port))
        self.buffer = b""
        self.connected = True
        self.status: int | None = None

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    def close(self) -> None:
        """
        Desconecta al cliente del server, mandando el mensaje apropiado
        antes de desconectar.
        """
        self.send('quit')
        self.status, message = self.read_response_line()
        if self.status != CODE_OK:
            logging.warning("Warning: quit no contesto ok, sino '%s'(%s)'.", message, self.status)
        self.connected = False
        self.s.close()

    def send(self, message: str, timeout: float | None = None) -> None:
        """
        Envía el mensaje 'message' al server, seguido por el terminador de
        línea del protocolo.

        Si se da un timeout, puede abortar con una excepción socket.timeout.

        También puede fallar con otras excepciones de socket.
        """
        self.s.settimeout(timeout)
        message += EOL  # Completar el mensaje con un fin de línea
        while message:
            logging.debug("Enviando el (resto del) mensaje %s.", repr(message))
            bytes_sent = self.s.send(message.encode("ascii"))
            if bytes_sent <= 0:
                raise OSError("No se pudieron enviar datos")
            message = message[bytes_sent:]

    def _recv(self, timeout: float | None = None) -> None:
        """
        Recibe datos y acumula en el buffer interno (bytes).

        Para uso privado del cliente.
        """
        self.s.settimeout(timeout)
        data = self.s.recv(4096)
        self.buffer += data

        if len(data) == 0:
            logging.info("El server interrumpió la conexión.")
            self.connected = False

    def read_line(self, timeout: float | None = None) -> str:
        """
        Espera datos hasta obtener una línea completa delimitada por el
        terminador del protocolo.

        Devuelve la línea, eliminando el terminador y los espacios en blanco
        al principio y al final.
        """
        while _CRLF not in self.buffer and self.connected:
            if timeout is not None:
                t1 = time.process_time()
            self._recv(timeout)
            if timeout is not None:
                t2 = time.process_time()
                timeout -= t2 - t1
                t1 = t2
        if _CRLF in self.buffer:
            line_b, _, self.buffer = self.buffer.partition(_CRLF)
            return line_b.decode("ascii").strip()
        else:
            self.connected = False
            return ""

    def read_exact_bytes(self, n: int, timeout: float | None = None) -> bytes:
        """Lee exactamente n bytes del flujo (buffer + socket)."""
        out = bytearray()
        remaining_timeout = timeout
        while len(out) < n:
            while len(self.buffer) == 0:
                if not self.connected:
                    raise OSError("conexión cerrada antes de leer el cuerpo")
                if remaining_timeout is not None:
                    t0 = time.process_time()
                self._recv(remaining_timeout)
                if remaining_timeout is not None:
                    remaining_timeout -= time.process_time() - t0
                    if remaining_timeout <= 0:
                        raise socket.timeout()
            take = min(n - len(out), len(self.buffer))
            out += self.buffer[:take]
            self.buffer = self.buffer[take:]
        return bytes(out)

    def read_response_line(self, timeout: float | None = None) -> tuple[int | None, str | None]:
        """
        Espera y parsea una línea de respuesta de un comando.

        Devuelve un par (int, str) con el código y el error, o
        (None, None) en caso de error.
        """
        result: tuple[int | None, str | None] = (None, None)
        response = self.read_line(timeout)
        if " " in response:
            code, message = response.split(None, 1)
            try:
                result = int(code), message
            except ValueError:
                pass
        else:
            logging.warning("Respuesta inválida: '%s'", response)
        return result

    def _read_slice_body(self, expect_plain_length: int, raw: bool) -> bytes:
        """Tras 0 OK: modo raw usa Content-Length + cuerpo binario; modo base64 usa líneas base64 terminadas en \\r\\n."""
        if raw:
            line = self.read_line()
            if not line.startswith(CONTENT_LENGTH_PREFIX):
                raise ValueError("se esperaba %r, recibió %r" % (CONTENT_LENGTH_PREFIX, line))
            n = int(line[len(CONTENT_LENGTH_PREFIX) :].strip())
            if self.read_line() != "":
                raise ValueError("después de Content-Length debe ir una línea vacía")
            wire = self.read_exact_bytes(n)
            if len(wire) != expect_plain_length:
                raise ValueError("modo raw: cuerpo %d bytes, se esperaban %d" % (len(wire), expect_plain_length))
            return wire
        if expect_plain_length == 0:
            self.read_line()
            return b""
        plain = b""
        while len(plain) < expect_plain_length:
            data = self.read_line()
            if not data:
                raise ValueError("payload base64 incompleto")
            plain += b64decode(data)
        if len(plain) != expect_plain_length:
            raise ValueError("base64 decodifica %d bytes, se esperaban %d" % (len(plain), expect_plain_length))
        return plain

    def file_lookup(self) -> list[str]:
        """
        Obtener el listado de archivos en el server. Devuelve una lista
        de strings.
        """
        result: list[str] = []
        self.send("get_file_listing")
        self.status, message = self.read_response_line()
        if self.status == CODE_OK:
            filename = self.read_line()
            while filename:
                logging.debug("Received filename %s", filename)
                result.append(filename)
                filename = self.read_line()
        else:
            logging.warning("Falló la solicitud de la lista de archivos (code=%s %s).", self.status, message)
        return result

    def get_metadata(self, filename: str) -> int | None:
        """
        Obtiene en el server el tamaño del archivo con el nombre dado.
        Devuelve None en caso de error.
        """
        try:
            self.send(f"get_metadata {filename}")
            self.status, message = self.read_response_line()
            if self.status == CODE_OK:
                size = int(self.read_line())
                return size
            return None
        except (ValueError, OSError, socket.timeout) as e:
            # Si hay un error de red o el servidor no devuelve un número
            logging.warning("Error obteniendo metadata: %s", e)
            return None

    def get_slice(self, filename: str, start: int, length: int, raw: bool = False) -> None:
        """
        Obtiene un trozo de un archivo en el server.

        El archivo es guardado localmente, en el directorio actual, con el
        mismo nombre que tiene en el server.
        """
        cmd = f"get_slice {filename} {start} {length}" + (" raw" if raw else "")
        self.send(cmd)
        self.status, message = self.read_response_line()
        if self.status == CODE_OK:
            try:
                data = self._read_slice_body(length, raw)
            except (ValueError, OSError, socket.timeout) as exc:
                logging.warning("Error leyendo payload de get_slice: %s", exc)
                self.connected = False
                return
            with open(filename, "wb") as output:
                output.write(data)
        else:
            logging.warning("El servidor indico un error al leer de %s.", filename)

    def retrieve(self, filename: str) -> None:
        """
        Obtiene un archivo completo desde el servidor.
        """
        size = self.get_metadata(filename)
        if self.status == CODE_OK:
            assert size is not None and size >= 0
            self.get_slice(filename, 0, size)
        elif self.status == FILE_NOT_FOUND:
            logging.info("El archivo solicitado no existe.")
        else:
            logging.warning("No se pudo obtener el archivo %s (code=%s).", filename, self.status)


def main() -> None:
    """
    Interfaz interactiva simple para el cliente: permite elegir un archivo
    y bajarlo.
    """
    DEBUG_LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    parser = argparse.ArgumentParser(usage="%(prog)s [options] server")
    parser.add_argument(
        "server",
        nargs="?",
        default=None,
        help="Dirección del servidor",
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Número de puerto TCP donde conectar",
    )
    parser.add_argument(
        "-v", "--verbose",
        dest="level",
        choices=DEBUG_LEVELS,
        default="ERROR",
        help="Nivel de depuración (ERROR, WARN, INFO, DEBUG)",
    )
    args = parser.parse_args()
    if args.server is None:
        parser.print_help()
        sys.exit(1)
    logging.getLogger().setLevel(DEBUG_LEVELS[args.level])
    try:
        client = Client(args.server, args.port)
    except (socket.error, socket.gaierror):
        sys.stderr.write("Error al conectarse\n")
        sys.exit(1)
    print("* Bienvenido al cliente HFTP - the Home-made File Transfer Protocol *\n"
          "* Estan disponibles los siguientes archivos:")
    files = client.file_lookup()
    for filename in files:
        print(filename)
    if client.status == CODE_OK:
        print("* Indique el nombre del archivo a descargar:")
        client.retrieve(input().strip())
    client.close()


if __name__ == '__main__':
    main()
