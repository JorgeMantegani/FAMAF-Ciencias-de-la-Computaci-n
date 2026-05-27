#!/usr/bin/env python3
# encoding: utf-8
"""
grade.py: autoevaluación del Lab 2 (HFTP).

Ejecuta tests funcionales (servidor bajo coverage), cobertura mínima sobre
connection/server, complejidad ciclomática y ruff. Mismos criterios que la
corrección automática.

Uso (desde el directorio del kickstart, con dependencias instaladas):
  python3 grade.py

Requisitos: pip install -r requirements.txt
"""

from __future__ import annotations

import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

# Umbrales (alineados con test_metrics.py y pyproject.toml)
MAX_COMPLEXITY = 17  # calibrado con radon cc sobre la solución de referencia
COVERAGE_MIN = 75  # calibrado: ~87 % en referencia (coverage run del proceso servidor)

DIR = Path(__file__).resolve().parent
CONNECT_HOST = "127.0.0.1"
PY_FILES = [DIR / "connection.py", DIR / "server.py"]


def _port() -> int:
    import constants

    return int(constants.DEFAULT_PORT)


def run(cmd: list[str], capture: bool = True, timeout: float | None = 120) -> tuple[int, str]:
    out = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        cwd=DIR,
        timeout=timeout,
    )
    return (out.returncode, (out.stdout or "") + (out.stderr or ""))


def wait_server_listening(timeout: float = 20.0) -> None:
    port = _port()
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = socket.create_connection((CONNECT_HOST, port), timeout=0.25)
            s.close()
            return
        except OSError:
            time.sleep(0.08)
    raise TimeoutError(f"No hubo respuesta en {CONNECT_HOST}:{port} tras {timeout}s")


def check_tests_and_coverage() -> tuple[bool, str, float | None]:
    """
    Arranca server.py bajo coverage, ejecuta pytest, envía SIGINT al servidor
    para que coverage escriba .coverage (SIGTERM no siempre persiste datos).
    """
    for p in DIR.glob(".coverage*"):
        try:
            p.unlink()
        except OSError:
            pass
    run([sys.executable, "-m", "coverage", "erase"], capture=True)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--source=connection,server",
            str(DIR / "server.py"),
            "-d",
            "testdata",
            "-p",
            str(_port()),
        ],
        cwd=DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pct: float | None = None
    try:
        try:
            wait_server_listening()
        except TimeoutError as e:
            if proc.poll() is not None:
                return (False, f"El servidor no arrancó (¿puerto {_port()} ocupado?).", None)
            proc.terminate()
            proc.wait(timeout=5)
            return (False, str(e), None)

        code, pytest_out = run(
            [
                sys.executable,
                "-m",
                "pytest",
                "server-test.py",
                "test_metrics.py",
                "-q",
                "--tb=no",
            ],
            capture=True,
            timeout=180,
        )

        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.terminate()
                proc.wait(timeout=5)

        rep_code, rep_out = run(
            [
                sys.executable,
                "-m",
                "coverage",
                "report",
                f"--fail-under={COVERAGE_MIN}",
            ],
            capture=True,
            timeout=60,
        )
        for line in rep_out.splitlines():
            if line.strip().startswith("TOTAL"):
                m = re.search(r"(\d+)%", line)
                if m:
                    pct = float(m.group(1))
                break
        if code != 0:
            return (False, "Fallan tests (pytest). " + pytest_out[-2000:], pct)
        if rep_code != 0:
            msg = f"Cobertura insuficiente (mínimo {COVERAGE_MIN}% sobre connection y server)."
            if pct is not None:
                msg += f" Actual: {pct}%."
            return (False, msg, pct)
        return (True, f"Tests OK. Cobertura connection+server: {pct}% (mínimo {COVERAGE_MIN}%).", pct)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def check_complexity() -> tuple[bool, str]:
    try:
        from radon.complexity import cc_visit
    except ImportError:
        return (False, "Falta instalar radon: pip install -r requirements.txt")
    over: list[tuple[str, int]] = []
    for path in PY_FILES:
        if not path.exists():
            return (False, f"No se encuentra {path.name}.")
        blocks = cc_visit(path.read_text(encoding="utf-8"))
        for b in blocks:
            if b.complexity > MAX_COMPLEXITY:
                over.append((f"{path.name}:{b.name}", b.complexity))
    if not over:
        return (True, f"Ninguna función supera complejidad {MAX_COMPLEXITY}.")
    detalle = ", ".join(f"{n}({c})" for n, c in over[:5])
    if len(over) > 5:
        detalle += f" ... y {len(over) - 5} más"
    return (False, f"Complejidad máxima permitida: {MAX_COMPLEXITY}. Superada en: {detalle}")


def check_ruff() -> tuple[bool, str]:
    args = [sys.executable, "-m", "ruff", "check"]
    for p in PY_FILES:
        if not p.exists():
            return (False, f"No se encuentra {p.name}.")
        args.append(str(p))
    args.append("--output-format=concise")
    code, out = run(args, capture=True, timeout=60)
    if code == 0:
        return (True, "Ruff: sin errores en connection.py ni server.py.")
    lines = [ln for ln in out.splitlines() if ln.strip() and "Found" not in ln]
    preview = "\n  ".join(lines[:8]) if lines else out.strip()
    return (False, f"Ruff reporta incidencias:\n  {preview}")


def main() -> int:
    print("=" * 60)
    print("  Lab 2 — Autoevaluación (grade.py)")
    print("=" * 60)
    print()

    results: list[tuple[str, bool, str]] = []

    print("1. Tests y cobertura (servidor bajo coverage) ... ", end="", flush=True)
    ok, msg, pct = check_tests_and_coverage()
    results.append(("Tests y cobertura", ok, msg))
    print("OK" if ok else "FALLO")
    for line in msg.splitlines():
        print("   ", line)
    print()

    print("2. Complejidad ciclomática ... ", end="", flush=True)
    ok, msg = check_complexity()
    results.append(("Complejidad ciclomática", ok, msg))
    print("OK" if ok else "FALLO")
    print("   ", msg)
    print()

    print("3. Análisis estático (ruff) ... ", end="", flush=True)
    ok, msg = check_ruff()
    results.append(("Ruff", ok, msg))
    print("OK" if ok else "FALLO")
    if not ok and "\n" in msg:
        for line in msg.split("\n")[1:]:
            print("  ", line)
    else:
        print("   ", msg)
    print()

    all_ok = all(r[1] for r in results)
    print("=" * 60)
    if all_ok:
        print("  RESULTADO: CUMPLE todas las condiciones de aprobación")
    else:
        print("  RESULTADO: NO CUMPLE alguna condición de aprobación")
        failed = [r[0] for r in results if not r[1]]
        print("  Revisar:", ", ".join(failed))
    print("=" * 60)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
