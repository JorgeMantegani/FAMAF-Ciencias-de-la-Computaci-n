#!/usr/bin/env python
# encoding: utf-8
# Revisión 2019 (a Python 3 y base64): Pablo Ventura
# Revisión 2014 Carlos Bederián
# Revisión 2011 Nicolás Wolovick
# Copyright 2008-2010 Natalia Bidart y Daniel Moisset
# $Id: server.py 656 2013-03-18 23:49:11Z bc $

import argparse
import socket
import sys
import connection
from constants import DEFAULT_ADDR, DEFAULT_DIR, DEFAULT_PORT


class Server:
    """
    El servidor, que crea y atiende el socket en la dirección y puerto
    especificados donde se reciben nuevas conexiones de clientes.
    """

    def __init__(
        self,
        addr: str = DEFAULT_ADDR,
        port: int = DEFAULT_PORT,
        directory: str = DEFAULT_DIR,
    ) -> None:
        # Se incluye addr, port y directory a instancia
        self.addr = addr
        self.port = port
        self.directory = directory

        # Se crea un nuevo objeto socket TCP, IPv4
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Escucha en puerto 19500 (default addr por ahora, escucha toda interfaz, chequear seguridad mas adelante)
        self.server_socket.bind((self.addr, self.port))
        self.server_socket.listen(5)

        # especificar que se trata de esta instancia, por si acaso
        print(f"Serving {self.directory} on {self.addr}:{self.port}.")

        # FALTA: Crear socket del servidor, configurarlo, asignarlo
        # a una dirección y puerto, etc.
        # revisar que la implementacion este bien

    def serve(self) -> None:
        """
        Loop principal del servidor. Se acepta una conexión a la vez
        y se espera a que concluya antes de seguir.
        """
        self.server_socket.settimeout(1.0) # timeout de 1 segundo para aceptar conexiones, para poder detectar KeyboardInterrupt

        try:
            while True:
                try:
                    # Acepta nueva conexion
                    c, a = self.server_socket.accept()
                    print(f"Establecida nueva conexion desde {a}.")
                except socket.timeout:
                    continue
                except socket.error as e:
                    print(f"\nError en conexion a cliente: {e}")
                    break #salimos del loop y se detiene el server
                try:
                    con = connection.Connection(c, self.directory)
                    con.handle()
                except Exception as e:
                    print(f"Error interno procesando al cliente {a}: {e}")
                finally:                # Cerrar socket de conexion
                    c.close()
                    print("conexion cerrada")
        except KeyboardInterrupt:
            print("\nServidor detenido por el usuario.")
        except socket.error:
            print(f"Error al conectar {socket.error}")
        finally:                    # Cerrar socket servidor
            self.server_socket.close()
            # FALTA:
            # ver si algo de esto funciona, ver mas tipos de exepciones


def main() -> None:
    """Parsea los argumentos y lanza el server"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p", "--port",
        help="Número de puerto TCP donde escuchar",
        type=int,
        default=DEFAULT_PORT,
    )
    parser.add_argument(
        "-a", "--address",
        help="Dirección donde escuchar",
        default=DEFAULT_ADDR,
    )
    parser.add_argument(
        "-d", "--datadir",
        help="Directorio compartido",
        default=DEFAULT_DIR,
    )
    args = parser.parse_args()
    try:
        server = Server(args.address, args.port, args.datadir)
        server.serve()
    except OSError as e:
        sys.stderr.write(f"Error al iniciar el servidor: {e}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
