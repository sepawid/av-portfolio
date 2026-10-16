import polars as pl
from dagster import AssetExecutionContext, asset

from av_portfolio.domain import SignClass, Weather
from av_portfolio.models.schemas import DetectionSchema

CONFIDENCE_THRESHOLD = 0.7
"""Predykcje z confidence poniżej progu są traktowane jak brak detekcji (NONE)."""

_CRITICAL_CLASSES = [SignClass.STOP.value, SignClass.YIELD.value]


def compute_kpi_flags(df: pl.DataFrame) -> pl.DataFrame:
    """Wektoryzowane obliczanie flag KPI (Polars Lazy API).

    Semantyka: najpierw wyliczana jest "efektywna predykcja" (`effective`) —
    predykcja z confidence poniżej CONFIDENCE_THRESHOLD jest odrzucana i liczona
    tak, jakby model nic nie wykrył (NONE). Dopiero na tej podstawie zapalane
    są flagi:

    - is_true_positive:   actual != NONE i effective == actual
    - is_true_negative:   actual == NONE i effective == NONE (poprawna cisza)
    - is_false_positive:  effective to inny znak niż actual (w tym phantom detection)
    - is_false_negative:  actual to znak, ale effective go nie potwierdza
    - is_critical_failure: przeoczony STOP/YIELD (FN) w złej pogodzie

    Błędna klasyfikacja znaku zapala jednocześnie FP i FN (konwencja flagowa).
    """
    return (
        df.lazy()
        .with_columns(
            effective_prediction=(
                pl.when(pl.col("confidence") >= CONFIDENCE_THRESHOLD)
                .then(pl.col("predicted_class"))
                .otherwise(int(SignClass.NONE))
            ),
        )
        .with_columns(
            [
                (
                    pl.when(
                        (pl.col("actual_class") != SignClass.NONE)
                        & (pl.col("effective_prediction") == pl.col("actual_class"))
                    )
                    .then(1)
                    .otherwise(0)
                ).alias("is_true_positive"),
                (
                    pl.when(
                        (pl.col("actual_class") == SignClass.NONE)
                        & (pl.col("effective_prediction") == SignClass.NONE)
                    )
                    .then(1)
                    .otherwise(0)
                ).alias("is_true_negative"),
                (
                    pl.when(
                        (pl.col("effective_prediction") != SignClass.NONE)
                        & (pl.col("effective_prediction") != pl.col("actual_class"))
                    )
                    .then(1)
                    .otherwise(0)
                ).alias("is_false_positive"),
                (
                    pl.when(
                        (pl.col("actual_class") != SignClass.NONE)
                        & (pl.col("effective_prediction") != pl.col("actual_class"))
                    )
                    .then(1)
                    .otherwise(0)
                ).alias("is_false_negative"),
                (
                    pl.when(
                        pl.col("actual_class").is_in(_CRITICAL_CLASSES)
                        & (pl.col("effective_prediction") != pl.col("actual_class"))
                        & (pl.col("weather") != Weather.SUNNY)
                    )
                    .then(1)
                    .otherwise(0)
                ).alias("is_critical_failure"),
            ]
        )
        .drop("effective_prediction")
        .collect()
    )


@asset
def validate_schema(context: AssetExecutionContext, ingest_logs: pl.DataFrame) -> pl.DataFrame:
    """Używa Pandery do walidacji schematu danych."""
    context.log.info("Walidacja schematu za pomocą Pandery...")
    return DetectionSchema.validate(ingest_logs)


@asset
def evaluate_metrics(context: AssetExecutionContext, validate_schema: pl.DataFrame) -> pl.DataFrame:
    """Oblicza flagi KPI na zwalidowanych danych."""
    context.log.info("Obliczanie metryk (Lazy Evaluation)...")
    return compute_kpi_flags(validate_schema)
