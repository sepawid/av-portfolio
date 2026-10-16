"""Runs the full KPI pipeline in-process — used by the demo GIF and the CI pipeline job.

Console logs from Dagster are quieted down to warnings; the point here is a clean,
readable summary (details live in the event log / Dagster UI). A failed quality
check makes the script exit non-zero, so CI acts as a quality gate.
"""

from __future__ import annotations

import time

from av_portfolio.definitions import defs

REPORT_FILE = "data/outputs/redash_db.sqlite"
QUIET_RUN_CONFIG = {"loggers": {"console": {"config": {"log_level": "WARNING"}}}}


def main() -> int:
    print("🚀 Starting AV Portfolio KPI Pipeline Demo...")
    started = time.perf_counter()
    result = defs.resolve_implicit_global_asset_job_def().execute_in_process(
        run_config=QUIET_RUN_CONFIG
    )
    elapsed = time.perf_counter() - started

    if not result.success:
        print(f"\n❌ Pipeline failed after {elapsed:.2f}s — see the error above.")
        return 1

    checks = result.get_asset_check_evaluations()
    materials = result.get_asset_materialization_events()
    passed = sum(1 for check in checks if check.passed)

    print(
        f"\n✅ Pipeline completed in {elapsed:.2f}s — "
        f"{len(materials)} assets materialized, {passed}/{len(checks)} quality checks passed"
    )

    failed = [check.check_name for check in checks if not check.passed]
    if failed:
        print("⚠️  Failed checks: " + ", ".join(failed))
        return 1

    print(f"📊 KPI report ready: {REPORT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
