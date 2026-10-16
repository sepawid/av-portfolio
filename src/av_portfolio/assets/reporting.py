import polars as pl
from dagster import AssetExecutionContext, asset

from av_portfolio.utils.paths import OUTPUTS_DIR, PROCESSED_DATA_DIR

RESULTS_FILE = PROCESSED_DATA_DIR / "results.parquet"
SQLITE_FILE = OUTPUTS_DIR / "redash_db.sqlite"


@asset
def export_parquet(context: AssetExecutionContext, evaluate_metrics: pl.DataFrame) -> str:
    """Zapisuje wynik .collect() do pliku results.parquet."""
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    evaluate_metrics.write_parquet(RESULTS_FILE)
    context.log.info(f"Wyniki zapisano do: {RESULTS_FILE}")
    return str(RESULTS_FILE)


@asset
def duckdb_bridge(context: AssetExecutionContext, export_parquet: str) -> None:
    """Ładuje Parquet i eksportuje widok agregujący do SQLite dla Redash."""
    import duckdb

    SQLITE_FILE.parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect()
    conn.execute("INSTALL sqlite; LOAD sqlite;")

    # Zapytanie agregujące
    agg_query = f"""
        SELECT
            weather,
            COUNT(*) as total_frames,
            SUM(is_true_positive) as tp,
            SUM(is_false_positive) as fp,
            SUM(is_false_negative) as fn,
            SUM(is_critical_failure) as critical_failures
        FROM read_parquet('{export_parquet}')
        GROUP BY weather
    """

    # Eksport do SQLite
    conn.execute(f"ATTACH '{SQLITE_FILE}' AS redash (TYPE SQLITE)")
    conn.execute("DROP TABLE IF EXISTS redash.kpi_report")
    conn.execute(f"CREATE TABLE redash.kpi_report AS {agg_query}")
    conn.execute("DETACH redash")

    context.log.info(f"Most DuckDB->SQLite gotowy: {SQLITE_FILE}")
    conn.close()
