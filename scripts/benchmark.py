#!/usr/bin/env python
"""Benchmark kluczowych etapów pipeline'u AV Portfolio.

Mierzy: generator 5M rekordów, ingest Protobuf → DataFrame, liczenie flag KPI,
cały pipeline end-to-end (demo_run) oraz testy jednostkowe. Wyniki zależą od
sprzętu — uruchom u siebie, aby porównać.

Uruchamianie (z katalogu repo):

    uv run python scripts/benchmark.py
"""

import platform
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from av_portfolio.assets.ingestion import load_detections
from av_portfolio.assets.metrics import compute_kpi_flags
from av_portfolio.utils.paths import RAW_DATA_DIR

REPO_ROOT = Path(__file__).resolve().parent.parent


def cpu_name() -> str:
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown CPU"


def timed(label: str, fn: Callable[[], Any]) -> tuple[str, float, Any]:
    start = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - start
    print(f"✔️  {label}: {elapsed:.2f} s")
    return label, elapsed, result


def run_subprocess(label: str, *args: str) -> tuple[str, float]:
    def _run() -> None:
        subprocess.run(
            [sys.executable, *args],
            check=True,
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    return timed(label, _run)[:2]


def main() -> None:
    print(f"🖥️  {cpu_name()} | {platform.system()} | Python {platform.python_version()}\n")

    results: list[tuple[str, float]] = []

    # 1. Generator (subprocess — realne użycie CLI)
    label, elapsed = run_subprocess("Generator: 5M rekordów → Protobuf", "generator.py")
    results.append((label, elapsed))

    # 2. Ingest + deserializacja Protobuf
    ingested: list[Any] = []
    label, elapsed, _ = timed(
        "Ingest: Protobuf → Polars DataFrame (5M)",
        lambda: ingested.append(load_detections(RAW_DATA_DIR / "detections.pb")),
    )
    df = ingested[0]
    results.append((label, elapsed))

    # 3. Flagowanie KPI (wektorowo)
    label, elapsed, _ = timed("KPI flags (compute_kpi_flags)", lambda: compute_kpi_flags(df))
    results.append((label, elapsed))

    # 4. Cały pipeline end-to-end
    label, elapsed = run_subprocess(
        "Pipeline end-to-end (ingest → walidacja → KPI → parquet → SQLite)", "demo_run.py"
    )
    results.append((label, elapsed))

    # 5. Testy jednostkowe
    label, elapsed = run_subprocess("Testy jednostkowe (pytest -q)", "-m", "pytest", "-q")
    results.append((label, elapsed))

    print("\n| Etap | Czas |")
    print("|---|---:|")
    for step_label, step_elapsed in results:
        print(f"| {step_label} | {step_elapsed:.2f} s |")
    print("\n💡 Czasy zależą od sprzętu — powyższa tabela to jeden pomiar lokalny.")


if __name__ == "__main__":
    main()
