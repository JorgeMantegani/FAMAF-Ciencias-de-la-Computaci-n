#!/usr/bin/env python3
# encoding: utf-8
"""
Tests de métricas de calidad: complejidad ciclomática y análisis estático (ruff).

Los tests funcionales están en server-test.py y requieren el servidor en marcha,
salvo que ejecuten la suite vía grade.py (que levanta el servidor bajo coverage).

Uso típico:
  python3 grade.py
  # o, con servidor ya corriendo en otra terminal:
  pytest server-test.py test_metrics.py -v
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Debe coincidir con grade.py (calibrado con radon sobre la solución de referencia).
MAX_CYCLOMATIC_COMPLEXITY = 17

DIR = Path(__file__).resolve().parent
STUDENT_FILES = [DIR / "connection.py", DIR / "server.py"]


def test_cyclomatic_complexity() -> None:
    import radon.complexity as radon_cc

    over: list[tuple[str, str, int]] = []
    for path in STUDENT_FILES:
        assert path.is_file(), f"Falta {path.name}"
        blocks = radon_cc.cc_visit(path.read_text(encoding="utf-8"))
        for b in blocks:
            if b.complexity > MAX_CYCLOMATIC_COMPLEXITY:
                over.append((path.name, b.name, b.complexity))
    assert not over, (
        f"Complejidad ciclomática máxima permitida: {MAX_CYCLOMATIC_COMPLEXITY}. "
        f"Superada en: {over}"
    )


def test_static_analysis_ruff() -> None:
    cmd = [sys.executable, "-m", "ruff", "check"]
    for path in STUDENT_FILES:
        assert path.is_file(), f"Falta {path.name}"
        cmd.append(str(path))
    cmd.append("--output-format=concise")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, (
        "Análisis estático (ruff) falló:\n" f"{result.stdout or result.stderr}"
    )


def test_coverage_is_checked_by_grade_py() -> None:
    """
    La cobertura mínima sobre connection+server se exige en grade.py usando
    `coverage run` en el proceso del servidor (no pytest-cov en el cliente).
    """
    assert True
