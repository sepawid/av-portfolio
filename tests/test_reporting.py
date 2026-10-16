"""Regression tests for the DuckDB -> SQLite BI bridge (`reporting.py`).

The bug this guards against: plain `SUM(...)` in DuckDB returns HUGEINT, which the
SQLite exporter maps to TEXT. Consumers (Redash, notebook) then saw strings —
matplotlib even turned the bar chart into uniform categorical steps.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import polars as pl
import pytest
from dagster import build_asset_context

from av_portfolio.assets import reporting

FLAG_COLUMNS = (
    "is_true_positive",
    "is_true_negative",
    "is_false_positive",
    "is_false_negative",
    "is_critical_failure",
    "is_poor_localization",
)
INT_COLUMNS = ("tp", "tn", "fp", "fn", "critical_failures", "poor_localizations")


def _sample_results() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "frame_id": list(range(1, 9)),
            "actual_class": [1, 1, 2, 2, 3, 3, 0, 0],
            "predicted_class": [1, 0, 2, 2, 0, 3, 0, 1],
            "confidence": [0.9, 0.5, 0.8, 0.9, 0.4, 0.95, 0.9, 0.6],
            "bbox_iou": [0.9, 0.3, 0.8, 0.85, 0.4, 0.9, 0.95, 0.2],
            "weather": [0, 0, 1, 1, 2, 2, 0, 2],
            "is_true_positive": [1, 0, 1, 1, 0, 1, 1, 0],
            "is_true_negative": [0, 0, 0, 0, 0, 0, 0, 0],
            "is_false_positive": [0, 0, 0, 0, 0, 0, 0, 1],
            "is_false_negative": [0, 1, 0, 0, 1, 0, 0, 0],
            "is_critical_failure": [0, 0, 0, 0, 1, 0, 0, 0],
            "is_poor_localization": [0, 1, 0, 0, 0, 0, 0, 0],
        },
        schema_overrides={column: pl.Int8 for column in FLAG_COLUMNS},
    )


def test_duckdb_bridge_keeps_aggregates_numeric_in_sqlite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parquet_path = tmp_path / "results.parquet"
    sqlite_path = tmp_path / "report.sqlite"
    source = _sample_results()
    source.write_parquet(parquet_path)

    monkeypatch.setattr(reporting, "SQLITE_FILE", sqlite_path)
    reporting.duckdb_bridge(build_asset_context(), export_parquet=str(parquet_path))

    con = sqlite3.connect(sqlite_path)
    declared = dict(
        con.execute("SELECT name, type FROM pragma_table_info('kpi_report')").fetchall()
    )
    report = pl.read_database("SELECT * FROM kpi_report", con)
    con.close()

    # 1. SQLite must store the summed columns as integers, not TEXT.
    for column in INT_COLUMNS:
        assert declared[column] == "BIGINT", f"{column} stored as {declared[column]}"

    # 2. Polars must read them back as integers.
    for column in INT_COLUMNS:
        assert report.schema[column] in (pl.Int32, pl.Int64), f"{column}: {report.schema[column]}"

    # 3. The overall row aggregates the raw flags.
    all_row = report.filter(pl.col("weather").is_null()).row(0, named=True)
    assert all_row["total_frames"] == source.height
    assert all_row["critical_failures"] == int(source["is_critical_failure"].sum())
    assert all_row["tp"] == int(source["is_true_positive"].sum())

    # 4. Per-weather rows are present (SUNNY/RAIN/FOG).
    assert report.filter(pl.col("weather").is_not_null()).height == source["weather"].n_unique()
