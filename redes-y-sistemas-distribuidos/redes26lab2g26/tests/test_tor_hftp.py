#!/usr/bin/env python3
# Tests para la guía Tor + HFTP: comprueban que el entorno y el flujo son correctos.
# Ejecutar desde la raíz del proyecto: python -m pytest tests/test_tor_hftp.py -v
# o: python tests/test_tor_hftp.py
# (repo docente: código en solucion/; kickstart: server.py y client.py en la raíz)

import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_solucion = os.path.join(REPO_ROOT, "solucion")
CODE_DIR = _solucion if os.path.isfile(os.path.join(_solucion, "server.py")) else REPO_ROOT
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

import client
import constants

HFTP_PORT = 19500
TORRC_PATH = "/etc/tor/torrc"
HOSTNAME_PATH = "/var/lib/tor/hftp_service/hostname"
ONION_PATTERN = re.compile(r"^[a-z0-9]{56}\.onion$")


class TestTorInstalled(unittest.TestCase):
    """Comprueba que Tor y torsocks estén disponibles (recomendado para la guía)."""

    def test_tor_installed(self) -> None:
        """Tor está instalado y accesible en el PATH."""
        result = subprocess.run(
            ["which", "tor"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            self.skipTest("Tor no está instalado. Instala con: sudo apt install tor")
        self.assertTrue(result.stdout.strip())

    def test_torsocks_installed(self) -> None:
        """torsocks está instalado (necesario para conectar el cliente a .onion)."""
        result = subprocess.run(
            ["which", "torsocks"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            self.skipTest("torsocks no está instalado. Instala con: sudo apt install torsocks")
        self.assertTrue(result.stdout.strip())


class TestTorConfig(unittest.TestCase):
    """Comprueba la configuración del onion service (si tenemos permisos de lectura)."""

    def test_torrc_has_hftp_service(self) -> None:
        """torrc contiene la configuración del servicio HFTP."""
        if not os.path.isfile(TORRC_PATH):
            self.skipTest(f"No se puede leer {TORRC_PATH} (no existe o sin permisos)")
        try:
            with open(TORRC_PATH) as f:
                content = f.read()
        except OSError:
            self.skipTest(f"No se puede leer {TORRC_PATH} (permiso denegado)")
        self.assertIn("HiddenServiceDir", content, "torrc debe definir HiddenServiceDir")
        self.assertIn("HiddenServicePort", content, "torrc debe definir HiddenServicePort")
        self.assertIn("19500", content, "torrc debe mapear el puerto 19500")

    def test_hostname_file_format(self) -> None:
        """Si existe el hostname de Tor, tiene formato .onion."""
        if not os.path.isfile(HOSTNAME_PATH):
            self.skipTest(f"No existe {HOSTNAME_PATH} (configura Tor y ejecuta setup_tor_hftp.sh)")
        try:
            with open(HOSTNAME_PATH) as f:
                hostname = f.read().strip()
        except OSError:
            self.skipTest(f"No se puede leer {HOSTNAME_PATH} (ejecuta con sudo o ajusta permisos)")
        self.assertRegex(
            hostname,
            ONION_PATTERN,
            f"El hostname '{hostname}' no tiene formato de dirección .onion (56 caracteres + .onion)",
        )


class TestServerTorStyle(unittest.TestCase):
    """Comprueba que el servidor HFTP escucha en localhost y responde (flujo usado con Tor)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="hftp_tor_test_")
        self.proc: subprocess.Popen | None = None

    def tearDown(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_server_listens_on_localhost(self) -> None:
        """El servidor arrancado con -a 127.0.0.1 -p 19500 acepta conexiones y responde."""
        server_py = os.path.join(CODE_DIR, "server.py")
        if not os.path.isfile(server_py):
            self.skipTest("No se encontró server.py (¿estás en la raíz del proyecto y completaste el servidor?)")
        self.proc = subprocess.Popen(
            [
                sys.executable,
                server_py,
                "-a", "127.0.0.1",
                "-p", str(HFTP_PORT),
                "-d", self.tmpdir,
            ],
            cwd=CODE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        # Esperar a que el socket esté en LISTEN
        for _ in range(25):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    s.connect(("127.0.0.1", HFTP_PORT))
                break
            except (socket.error, OSError):
                time.sleep(0.2)
        else:
            self.proc.terminate()
            self.fail("El servidor no aceptó conexiones en 127.0.0.1:19500 en 5 s")
        # Dar tiempo al servidor a cerrar la conexión de prueba y volver a accept()
        time.sleep(0.6)
        # Cliente HFTP: listar archivos (lista vacía) y quit
        c = client.Client("127.0.0.1", HFTP_PORT)
        files = c.file_lookup()
        self.assertEqual(c.status, constants.CODE_OK)
        self.assertIsInstance(files, list)
        c.close()

    def test_server_responds_get_file_listing(self) -> None:
        """Con un archivo en el directorio, get_file_listing lo devuelve."""
        server_py = os.path.join(CODE_DIR, "server.py")
        if not os.path.isfile(server_py):
            self.skipTest("No se encontró server.py (¿estás en la raíz del proyecto y completaste el servidor?)")
        with open(os.path.join(self.tmpdir, "hola.txt"), "w") as f:
            f.write("mundo")
        self.proc = subprocess.Popen(
            [
                sys.executable,
                server_py,
                "-a", "127.0.0.1",
                "-p", str(HFTP_PORT),
                "-d", self.tmpdir,
            ],
            cwd=CODE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        for _ in range(25):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    s.connect(("127.0.0.1", HFTP_PORT))
                break
            except (socket.error, OSError):
                time.sleep(0.2)
        else:
            self.proc.terminate()
            self.fail("El servidor no aceptó conexiones en 127.0.0.1:19500")
        time.sleep(0.6)
        c = client.Client("127.0.0.1", HFTP_PORT)
        files = c.file_lookup()
        c.close()
        self.assertEqual(c.status, constants.CODE_OK)
        self.assertIn("hola.txt", files)

    def test_server_get_metadata(self) -> None:
        """get_metadata devuelve el tamaño correcto del archivo."""
        server_py = os.path.join(CODE_DIR, "server.py")
        if not os.path.isfile(server_py):
            self.skipTest("No se encontró server.py (¿estás en la raíz del proyecto y completaste el servidor?)")
        content = b"abc\x00def\n"
        with open(os.path.join(self.tmpdir, "meta.txt"), "wb") as f:
            f.write(content)
        self.proc = subprocess.Popen(
            [
                sys.executable,
                server_py,
                "-a", "127.0.0.1",
                "-p", str(HFTP_PORT),
                "-d", self.tmpdir,
            ],
            cwd=CODE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        for _ in range(25):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    s.connect(("127.0.0.1", HFTP_PORT))
                break
            except (socket.error, OSError):
                time.sleep(0.2)
        else:
            self.proc.terminate()
            self.fail("Servidor no aceptó conexiones")
        time.sleep(0.6)
        c = client.Client("127.0.0.1", HFTP_PORT)
        size = c.get_metadata("meta.txt")
        c.close()
        self.assertEqual(c.status, constants.CODE_OK)
        self.assertEqual(size, len(content))

    def test_server_retrieve_downloads_file_with_correct_content(self) -> None:
        """retrieve() descarga el archivo y el contenido coincide con el del servidor."""
        server_py = os.path.join(CODE_DIR, "server.py")
        if not os.path.isfile(server_py):
            self.skipTest("No se encontró server.py (¿estás en la raíz del proyecto y completaste el servidor?)")
        expected_content = "contenido de prueba para Tor\n"
        with open(os.path.join(self.tmpdir, "descarga.txt"), "w") as f:
            f.write(expected_content)
        self.proc = subprocess.Popen(
            [
                sys.executable,
                server_py,
                "-a", "127.0.0.1",
                "-p", str(HFTP_PORT),
                "-d", self.tmpdir,
            ],
            cwd=CODE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        for _ in range(25):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    s.connect(("127.0.0.1", HFTP_PORT))
                break
            except (socket.error, OSError):
                time.sleep(0.2)
        else:
            self.proc.terminate()
            self.fail("Servidor no aceptó conexiones")
        time.sleep(0.6)
        # El cliente escribe en el cwd; usamos un subdir para no pisar el tmpdir del servidor
        download_dir = tempfile.mkdtemp(prefix="hftp_download_", dir=self.tmpdir)
        prev_cwd = os.getcwd()
        try:
            os.chdir(download_dir)
            c = client.Client("127.0.0.1", HFTP_PORT)
            c.retrieve("descarga.txt")
            c.close()
            self.assertEqual(c.status, constants.CODE_OK)
            downloaded = os.path.join(download_dir, "descarga.txt")
            self.assertTrue(os.path.isfile(downloaded), "El archivo descargado no existe")
            with open(downloaded) as f:
                self.assertEqual(f.read(), expected_content, "El contenido descargado no coincide")
        finally:
            os.chdir(prev_cwd)
            shutil.rmtree(download_dir, ignore_errors=True)


def _get_onion_for_test() -> str | None:
    """Obtiene la dirección .onion para tests e2e: variable de entorno o archivo hostname."""
    onion = os.environ.get("ONION", "").strip()
    if onion and onion.endswith(".onion"):
        return onion
    if os.path.isfile(HOSTNAME_PATH):
        try:
            with open(HOSTNAME_PATH) as f:
                return f.read().strip() or None
        except OSError:
            pass
    return None


class TestTorE2E(unittest.TestCase):
    """Prueba real vía Tor: cliente conecta a .onion y descarga un archivo. Se omite si no hay Tor/ONION."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="hftp_tor_e2e_")
        self.proc: subprocess.Popen | None = None

    def tearDown(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_client_via_torsocks_downloads_file_from_onion(self) -> None:
        """Cliente con torsocks conecta a la .onion, lista archivos y descarga; el contenido es correcto."""
        onion = _get_onion_for_test()
        if not onion:
            self.skipTest(
                "Sin dirección .onion (exporta ONION=tu.onion o configura Tor y ejecuta setup_tor_hftp.sh)"
            )
        if subprocess.run(["which", "torsocks"], capture_output=True).returncode != 0:
            self.skipTest("torsocks no está instalado")
        server_py = os.path.join(CODE_DIR, "server.py")
        if not os.path.isfile(server_py):
            self.skipTest("No se encontró server.py (¿estás en la raíz del proyecto y completaste el servidor?)")
        # Archivo de prueba
        expected = "contenido e2e vía Tor\n"
        with open(os.path.join(self.tmpdir, "archivo.txt"), "w") as f:
            f.write(expected)
        self.proc = subprocess.Popen(
            [
                sys.executable,
                server_py,
                "-a", "127.0.0.1",
                "-p", str(HFTP_PORT),
                "-d", self.tmpdir,
            ],
            cwd=CODE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        for _ in range(30):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    s.connect(("127.0.0.1", HFTP_PORT))
                break
            except (socket.error, OSError):
                time.sleep(0.2)
        else:
            self.proc.terminate()
            self.fail("El servidor no aceptó conexiones en 127.0.0.1:19500")
        time.sleep(0.8)
        # Cliente vía torsocks hacia la .onion
        download_dir = tempfile.mkdtemp(prefix="download_", dir=self.tmpdir)
        client_py = os.path.join(CODE_DIR, "client.py")
        result = subprocess.run(
            ["torsocks", sys.executable, client_py, onion, "-p", str(HFTP_PORT)],
            cwd=download_dir,
            input="archivo.txt\n",
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            self.proc.terminate()
            self.fail(
                f"Cliente vía torsocks falló (returncode={result.returncode}). "
                f"stderr: {result.stderr!r}"
            )
        downloaded = os.path.join(download_dir, "archivo.txt")
        self.assertTrue(os.path.isfile(downloaded), "No se creó el archivo descargado")
        with open(downloaded) as f:
            self.assertEqual(f.read(), expected, "El contenido descargado no coincide")


def run_script(script: str, cwd: str | None = None) -> tuple[int, str, str]:
    """Ejecuta un script bash y devuelve (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["bash", "-e", script],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


class TestScripts(unittest.TestCase):
    """Comprueba que los scripts de la guía existen y son ejecutables."""

    def test_setup_script_exists(self) -> None:
        path = os.path.join(REPO_ROOT, "scripts", "tor", "setup_tor_hftp.sh")
        self.assertTrue(os.path.isfile(path), f"Falta {path}")

    def test_get_onion_hostname_script_exists(self) -> None:
        path = os.path.join(REPO_ROOT, "scripts", "tor", "get_onion_hostname.sh")
        self.assertTrue(os.path.isfile(path), f"Falta {path}")

    def test_run_server_tor_script_exists(self) -> None:
        path = os.path.join(REPO_ROOT, "scripts", "tor", "run_server_tor.sh")
        self.assertTrue(os.path.isfile(path), f"Falta {path}")

    def test_run_client_tor_script_exists(self) -> None:
        path = os.path.join(REPO_ROOT, "scripts", "tor", "run_client_tor.sh")
        self.assertTrue(os.path.isfile(path), f"Falta {path}")

    def test_run_server_tor_script_starts_server(self) -> None:
        """run_server_tor.sh arranca el servidor (salida por stdin para terminarlo)."""
        script = os.path.join(REPO_ROOT, "scripts", "tor", "run_server_tor.sh")
        if not os.path.isfile(script):
            self.skipTest("Falta run_server_tor.sh")
        tmpdir = tempfile.mkdtemp(prefix="hftp_tor_run_")
        try:
            # Directorio de datos relativo al directorio donde está server.py (run_server_tor.sh)
            testdata = os.path.join(CODE_DIR, "testdata_tor_script")
            os.makedirs(testdata, exist_ok=True)
            try:
                proc = subprocess.Popen(
                    ["bash", script, "testdata_tor_script"],
                    cwd=REPO_ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                )
                time.sleep(1.5)
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(2)
                        s.connect(("127.0.0.1", HFTP_PORT))
                except (socket.error, OSError):
                    proc.terminate()
                    _, err = proc.communicate(timeout=3)
                    self.fail(f"El servidor no escuchaba en 19500. stderr: {err.decode()}")
                proc.terminate()
                proc.wait(timeout=5)
            finally:
                shutil.rmtree(testdata, ignore_errors=True)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
