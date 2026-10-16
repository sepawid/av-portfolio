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
    """Ładuje Parquet i eksportuje zagregowany raport KPI do SQLite dla Redash.

    Raport zawiera wiersze per pogoda oraz wiersz zbiorczy (weather IS NULL,
    label 'ALL') wyliczony przez GROUPING SETS, wraz z metrykami pochodnymi
    precision/recall/f1.
    """
    import duckdb

    SQLITE_FILE.parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect()
    conn.execute("INSTALL sqlite; LOAD sqlite;")

    # Agregacja per pogoda + wiersz zbiorczy; wartości NULL-safe (NULLIF).
    agg_query = f"""
        SELECT
            CASE
                WHEN weather IS NULL THEN 'ALL'
                WHEN weather = 0 THEN 'SUNNY'
                WHEN weather = 1 THEN 'RAIN'
                WHEN weather = 2 THEN 'FOG'
                ELSE 'UNKNOWN'
            END AS weather_label,
            weather,
            COUNT(*) AS total_frames,
            SUM(is_true_positive) AS tp,
            SUM(is_true_negative) AS tn,
            SUM(is_false_positive) AS fp,
            SUM(is_false_negative) AS fn,
            SUM(is_critical_failure) AS critical_failures,
            ROUND(
                SUM(is_true_positive) / NULLIF(SUM(is_true_positive) + SUM(is_false_positive), 0),
                4
            ) AS precision,
            ROUND(
                SUM(is_true_positive) / NULLIF(SUM(is_true_positive) + SUM(is_false_negative), 0),
                4
            ) AS recall,
            ROUND(
                2 * SUM(is_true_positive)
                / NULLIF(
                    2 * SUM(is_true_positive) + SUM(is_false_positive) + SUM(is_false_negative),
                    0
                ),
                4
            ) AS f1
        FROM read_parquet('{export_parquet}')
        GROUP BY GROUPING SETS ((weather), ())
        ORDER BY weather NULLS LAST
    """

    # Eksport do SQLite
    conn.execute(f"ATTACH '{SQLITE_FILE}' AS redash (TYPE SQLITE)")
    conn.execute("DROP TABLE IF EXISTS redash.kpi_report")
    conn.execute(f"CREATE TABLE redash.kpi_report AS {agg_query}")
    conn.execute("DETACH redash")

    context.log.info(f"Most DuckDB->SQLite gotowy: {SQLITE_FILE}")
    conn.close()
