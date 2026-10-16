"""Smoke tests for the CI KPI summary renderer (`scripts/ci_kpi_summary.py`)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ci_kpi_summary  # noqa: E402

CREATE_TABLE = """
    CREATE TABLE kpi_report (
        weather_label TEXT, weather INTEGER, total_frames INTEGER,
        tp INTEGER, tn INTEGER, fp INTEGER, fn INTEGER,
        critical_failures INTEGER, poor_localizations INTEGER,
        avg_iou_tp REAL, precision REAL, recall REAL, f1 REAL
    )
"""


def _fetch_rows(tmp_path: Path, *values: tuple[object, ...]) -> list[sqlite3.Row]:
    con = sqlite3.connect(tmp_path / "report.sqlite")
    con.execute(CREATE_TABLE)
    placeholders = ", ".join("?" * 13)
    con.executemany(f"INSERT INTO kpi_report VALUES ({placeholders})", values)
    con.row_factory = sqlite3.Row
    rows = con.execute(f"SELECT * FROM kpi_report {ci_kpi_summary.WEATHER_ORDER}").fetchall()
    con.close()
    return rows


def test_summary_renders_headline_table_and_failed_budget(tmp_path: Path) -> None:
    rows = _fetch_rows(
        tmp_path,
        ("SUNNY", 0, 1_500, 900, 50, 20, 80, 10, 5, 0.9, 0.98, 0.9, 0.94),
        ("ALL", None, 1_500, 900, 50, 20, 80, 60, 5, 0.9, 0.98, 0.9, 0.94),
    )

    text = ci_kpi_summary.render_summary(rows)

    assert "1,500 frames" in text
    assert "| SUNNY | 1,500 |" in text
    assert "| ALL | 1,500 |" in text
    # 60 / (900 + 80) = 6.12% > 5% budget -> failure marker
    assert "6.12% ❌" in text


def test_summary_marks_budget_pass(tmp_path: Path) -> None:
    rows = _fetch_rows(
        tmp_path,
        ("ALL", None, 1_000, 900, 50, 20, 80, 4, 5, 0.9, 0.98, 0.9, 0.94),
    )

    text = ci_kpi_summary.render_summary(rows)

    # 4 / (900 + 80) = 0.41% < 5% budget -> pass marker
    assert "0.41% ✅" in text
