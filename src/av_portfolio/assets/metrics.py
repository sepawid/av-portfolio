import polars as pl
from dagster import AssetExecutionContext, asset

from av_portfolio.models.schemas import DetectionSchema


@asset
def validate_schema(context: AssetExecutionContext, ingest_logs: pl.DataFrame) -> pl.DataFrame:
    """Używa Pandery do walidacji schematu danych."""
    context.log.info("Walidacja schematu za pomocą Pandery...")
    return DetectionSchema.validate(ingest_logs)


@asset
def evaluate_metrics(context: AssetExecutionContext, validate_schema: pl.DataFrame) -> pl.DataFrame:
    """Wektoryzowane obliczanie KPI z użyciem Polars Lazy API."""
    context.log.info("Obliczanie metryk (Lazy Evaluation)...")

    # STOP=1, YIELD=2, NONE=0, SUNNY=0

    return (
        validate_schema.lazy()
        .with_columns(
            [
                # True Positive (Model trafił idealnie w punkt)
                (
                    pl.when(
                        (pl.col("predicted_class") == pl.col("actual_class"))
                        & (pl.col("confidence") > 0.7)
                    )
                    .then(1)
                    .otherwise(0)
                ).alias("is_true_positive"),
                # False Positive (Przewidziano znak, którego nie ma)
                (
                    pl.when(
                        (pl.col("predicted_class") != pl.col("actual_class"))
                        & (pl.col("predicted_class") != 0)
                    )
                    .then(1)
                    .otherwise(0)
                ).alias("is_false_positive"),
                # False Negative (Przeoczono istniejący znak)
                (
                    pl.when(
                        (pl.col("predicted_class") != pl.col("actual_class"))
                        & (pl.col("actual_class") != 0)
                    )
                    .then(1)
                    .otherwise(0)
                ).alias("is_false_negative"),
                # Critical Failure (Przeoczono STOP/YIELD w złej pogodzie)
                (
                    pl.when(
                        pl.col("actual_class").is_in([1, 2])
                        & (pl.col("predicted_class") != pl.col("actual_class"))
                        & (pl.col("weather") != 0)
                    )
                    .then(1)
                    .otherwise(0)
                ).alias("is_critical_failure"),
            ]
        )
        .collect()
    )
