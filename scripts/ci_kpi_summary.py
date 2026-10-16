"""Renders a Markdown KPI summary from the SQLite report — used by the CI pipeline job.

Usage (GitHub Actions):
    uv run python scripts/ci_kpi_summary.py | tee -a "$GITHUB_STEP_SUMMARY"

The same content lands in the job logs and in the run's Summary tab, so the KPI
numbers are visible right in the Actions UI without downloading any artifacts.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SQLITE_FILE = Path("data/outputs/redash_db.sqlite")
MAX_CRITICAL_FAILURE_RATE = 0.05  # keep in sync with checks.MAX_CRITICAL_FAILURE_RATE

# Wiersze per pogoda, na końcu zbiorczy 'ALL' (NULL) — przenośne dla starego SQLite.
WEATHER_ORDER = "ORDER BY weather IS NULL, weather"


def render_summary(rows: list[sqlite3.Row]) -> str:
    all_row = next(row for row in rows if row["weather"] is None)
    rate = all_row["critical_failures"] / (all_row["tp"] + all_row["fn"])
    ok = rate < MAX_CRITICAL_FAILURE_RATE

    lines = [
        "## 📊 TSR KPI Pipeline — run summary",
        "",
        f"**{all_row['total_frames']:,} frames** evaluated · deterministic data (SEED=42) · "
        "full report attached as the `kpi-report-sqlite` artifact",
        "",
        "| Global KPI | Value |",
        "| --- | --- |",
        f"| Precision | {all_row['precision']:.4f} |",
        f"| Recall | {all_row['recall']:.4f} |",
        f"| F1 | {all_row['f1']:.4f} |",
        f"| Critical failures (missed STOP/YIELD) | {all_row['critical_failures']:,} |",
        f"| Critical failure rate (budget {MAX_CRITICAL_FAILURE_RATE:.0%}) "
        f"| {rate:.2%} {'✅' if ok else '❌'} |",
        f"| Poor localizations | {all_row['poor_localizations']:,} |",
        f"| Avg IoU (TP) | {all_row['avg_iou_tp']:.4f} |",
        "",
        "| Weather | Frames | TP | FP | FN | Critical | Precision | Recall | F1 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['weather_label']} | {row['total_frames']:,} | {row['tp']:,} "
            f"| {row['fp']:,} | {row['fn']:,} | {row['critical_failures']:,} "
            f"| {row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} |"
        )
    return "\n".join(lines)


def main() -> int:
    if not SQLITE_FILE.exists():
        print(f"::error::KPI report not found: {SQLITE_FILE}")
        return 1

    con = sqlite3.connect(f"file:{SQLITE_FILE}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(f"SELECT * FROM kpi_report {WEATHER_ORDER}").fetchall()
    con.close()

    print(render_summary(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
