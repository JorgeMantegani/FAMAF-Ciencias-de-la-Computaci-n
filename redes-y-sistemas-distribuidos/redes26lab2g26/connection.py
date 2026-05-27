# encoding: utf-8
# Revisión 2019 (a Python 3 y base64): Pablo Ventura
# Copyright 2014 Carlos Bederián
# $Id: connection.py 455 2011-05-01 00:32:09Z carlos $

import os
import socket
# from base64 import b64encode

from constants import (
    BAD_EOL,
    # BAD_OFFSET,
    BAD_REQUEST,
    CODE_OK,
    COMMANDS,
    CONTENT_LENGTH_PREFIX,
    EOL,
    FILE_NOT_FOUND,
    INTERNAL_ERROR,
    INVALID_ARGUMENTS,
    INVALID_COMMAND,
    BAD_OFFSET,
    error_messages,
    # fatal_status,
)


class Connection:
    """
    Conexión punto a punto entre el servidor y un cliente.
    Se encarga de satisfacer los pedidos del cliente hasta
    que termina la conexión.
    """

    def __init__(self, sock: socket.socket, directory: str) -> None:
        # Inicializa datos de conexion
        self.sock = sock
        self.directory = directory
        self.buffer = b""                           # buffer para datos y checkeo de \r\n
        # FALTA: Inicializar atributos de Connection
        # hay que ver si esto esta bien y si es suficiente

        self.command_handlers = {
            "quit": self._handle_quit,
            "help": self._handle_help,
            "get_file_listing": self._handle_get_file_listing_cmd,
            "get_metadata": self._handle_get_metadata_cmd,
            "get_slice": self._handle_get_slice_cmd,
        }

    def _recv_line(self) -> tuple[str | None, int | None]:
        """
        Funcion auxiliar para recibir comandos del usuario.
        Devuelve un string de ascii decodificado sin EOL. Devuelve None en caso de error.
        """
        while b"\r\n" not in self.buffer:
            try:
                data = self.sock.recv(4096)  # medio arbitrario
                if not data:
                    return None, None  # conexion cerrada por el cliente
                self.buffer += data  # todo el mensaje recibido va a parar al buffer
            except socket.error:
                return None, INTERNAL_ERROR

            # Si llega LF sin CRLF, el EOL es invalido.
            if b"\n" in self.buffer and b"\r\n" not in self.buffer:
                return None, BAD_EOL

        line2, _, self.buffer = self.buffer.partition(b"\r\n")

        # Si dentro de la linea hay LF suelto, el EOL es invalido.
        if b"\n" in line2:
            return None, BAD_EOL

        try:
            line = line2.decode("ascii")
        except UnicodeDecodeError:
            return None, BAD_REQUEST

        if line.strip() == "":
            return None, BAD_REQUEST

        return line.strip(), None


    def _send_line(self, line: str) -> bool:
        """
        Funcion auxiliar, envia line + EOL al cliente codificado en ascii.
        Devuelve False en caso de haber error, True si el mensaje pasa sin errores.
        """
        try:
            self.sock.sendall((line + EOL).encode('ascii'))    #linea de respuesta + \r\n
            return True                                     #esta linea es de control, error catching mas adelante
        except socket.error:
            return False


    def _process_command(self, command_line: str) -> bool:
        """
        Funcion auxiliar para procesamiento de comandos.
        Devuelve False en caso de error, True si se ejecuta sin errores.
        """

        parts = command_line.split()
        if not parts:                #el cliente envio un comando vacio, la conexion se mantiene
            self._send_line(f"{INVALID_COMMAND} {error_messages[INVALID_COMMAND]}")
            return True


        cmd = parts[0].lower()
        if cmd in self.command_handlers:
            return self.command_handlers[cmd](parts)
        else:
            self._send_line(f"{INVALID_COMMAND} {error_messages[INVALID_COMMAND]}")
            return True

    def _handle_quit(self, parts: list[str]) -> bool:
        if len(parts) != 1:
            self._send_line(f"{INVALID_ARGUMENTS} {error_messages[INVALID_ARGUMENTS]}")
            return True
        self._send_line(f"{CODE_OK} OK")
        return False

    def _handle_help(self, parts: list[str]) -> bool:
        if len(parts) != 1:
            self._send_line(f"{INVALID_ARGUMENTS} {error_messages[INVALID_ARGUMENTS]}")
            return True
        if not self._send_line(f"{CODE_OK} OK"):
            return False
        for command in COMMANDS:
            if not self._send_line(command):
                return False
        self._send_line("")
        return True

    def _handle_get_file_listing_cmd(self, parts: list[str]) -> bool:
        if len(parts) != 1:
            self._send_line(f"{INVALID_ARGUMENTS} {error_messages[INVALID_ARGUMENTS]}")
            return True
        return self._handle_get_file_listing()

    def _handle_get_metadata_cmd(self, parts: list[str]) -> bool:
        if len(parts) != 2:
            self._send_line(f"{INVALID_ARGUMENTS} {error_messages[INVALID_ARGUMENTS]}")
            return True
        return self._handle_metadata(parts[1])

    def _handle_get_slice_cmd(self, parts: list[str]) -> bool:
        # Comando GET_SLICE
        # checkeo de argumentos
        # valid_args = True
        length = len(parts)
        if length not in (4, 5):
            self._send_line(f"{INVALID_ARGUMENTS} {error_messages[INVALID_ARGUMENTS]}")
            return True
        try:
            arg1 = int(parts[2])
            arg2 = int(parts[3])
            if arg1 < 0 or arg2 < 0:
                self._send_line(f"{INVALID_ARGUMENTS} {error_messages[INVALID_ARGUMENTS]}")
                return True
        except ValueError:
            self._send_line(f"{INVALID_ARGUMENTS} {error_messages[INVALID_ARGUMENTS]}")
            return True
        # vemos los 3 posibles casos
        if length == 4:
            return self._handle_get_slice(parts[1],arg1, arg2, False)
        elif length == 5:
            if parts[4].lower() != "raw":
                self._send_line(f"{INVALID_ARGUMENTS} {error_messages[INVALID_ARGUMENTS]}")
                return True
            return self._handle_get_slice(parts[1], arg1, arg2, True)
        else:
            self._send_line(f"{INVALID_ARGUMENTS} {error_messages[INVALID_ARGUMENTS]}")
            return True

    def handle(self) -> None:
        """
        Atiende eventos de la conexión hasta que termina.
        """
        while True:
            # recibe comandos
            command_line, err = self._recv_line()
            if err is not None:
                self._send_line(f"{err} {error_messages[err]}")
                break
            if command_line is None:
                break  # el cliente cerro conexion

            if not self._process_command(command_line):
                break                       #error o quit, diferenciar aca o mandar mensaje en _process_command?



    # A partir de aca puede haber errores fatales
    def _handle_get_file_listing(self) -> bool:
        try:
            files = []          # se obtiene lista de archivos(solo archivos)
            for item in os.listdir(self.directory):
                item_path = os.path.join(self.directory, item)
                if os.path.isfile(item_path):
                    files.append(item)


            # protocolo pide respuesta OK
            if not self._send_line(f"{CODE_OK} OK"):
                return False


            # se envia cada nombre de archivo por separado
            for filename in files:
                if not self._send_line(filename):
                    return False


            # fin del payload marcado con linea vacia
            if not self._send_line(""):
                return False
            return True
        except OSError:
            self._send_line(f"{INTERNAL_ERROR} {error_messages[INTERNAL_ERROR]}")
            return True
        except Exception:
            self._send_line(f"{INTERNAL_ERROR} {error_messages[INTERNAL_ERROR]}")
            return True

    def _handle_metadata(self, filename: str) -> bool:
        # WIP: enviar tamaño de archivo.       CUIDADO CON PATH TRAVERSAL!!!
        safe_path = os.path.normpath(os.path.join(self.directory, filename))
        if not safe_path.startswith(self.directory):
            # aca hubo un caso de path traversal, gente fea cochina
            self._send_line(f"{FILE_NOT_FOUND} {error_messages[FILE_NOT_FOUND]}")
            return True


        try:
            file_size = os.path.getsize(safe_path)
            # protocolo pide respuesta OK
            if not self._send_line(f"{CODE_OK} OK"):
                return False
            # envia tamaño
            if not self._send_line(str(file_size)):
                return False
            return True


        except (FileNotFoundError, OSError):
            self._send_line(f"{FILE_NOT_FOUND} {error_messages[FILE_NOT_FOUND]}")
            return True


    def _handle_get_slice(self, filename: str, offset: int, size: int, raw: bool) -> bool:
        import os
        import base64

        #para evitar path traversal, normalizo
        filepath = os.path.normpath(os.path.join(self.directory, filename))
        if not filepath.startswith(self.directory):
            self._send_line(f"{FILE_NOT_FOUND} {error_messages[FILE_NOT_FOUND]}")
            return True


        #verifico que exista
        if not os.path.isfile(filepath):
            self._send_line(f"{FILE_NOT_FOUND} {error_messages[FILE_NOT_FOUND]}")
            return True


        #verifico offset y size
        file_size = os.path.getsize(filepath)
        if offset + size > file_size:
            #mal offset
            self._send_line(f"{BAD_OFFSET} {error_messages[BAD_OFFSET]}")
            return True


        #leer archivo y mandar datos
        try:
            with open(filepath, "rb") as f: #with cierra el archivo luego de este bloque de codigo, rb es read binary
                f.seek(offset)
                data = f.read(size)


                if raw:
                    #modo raw, se manda el contenido sin cambiar
                    if not self._send_line(f"{CODE_OK} OK"):
                        return False
                    if not self._send_line(f"{CONTENT_LENGTH_PREFIX} {size}"):
                        return False
                    if not self._send_line(""):
                        return False
                    try:
                        self.sock.sendall(data) #sendall es para mandar todo el contenido, send puede no mandar todo
                    except socket.error:
                        return False






                else:
                    #modo base 64
                    b64_data = base64.b64encode(data).decode('ascii') #codifico a base64 y luego a ascii para enviar
                    if not self._send_line(f"{CODE_OK} OK"):
                        return False
                    if not self._send_line(b64_data):
                        return False

        except PermissionError:
            self._send_line(f"{INTERNAL_ERROR} {error_messages[INTERNAL_ERROR]}")
        except Exception:
            self._send_line(f"{INTERNAL_ERROR} {error_messages[INTERNAL_ERROR]}")

        return True

