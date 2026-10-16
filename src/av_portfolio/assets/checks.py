import polars as pl
from dagster import AssetCheckResult, asset_check

from av_portfolio.assets.metrics import evaluate_metrics

FLAG_COLUMNS = [
    "is_true_positive",
    "is_true_negative",
    "is_false_positive",
    "is_false_negative",
    "is_critical_failure",
    "is_poor_localization",
]

MIN_EXPECTED_ROWS = 4_900_000
MAX_CRITICAL_FAILURE_RATE = 0.05


def flag_integrity(df: pl.DataFrame) -> tuple[int, int]:
    """Zwraca (liczba nulli, liczba wartości spoza {0, 1}) w kolumnach flag KPI."""
    flags = df.select(FLAG_COLUMNS)
    nulls = flags.null_count().sum_horizontal().item()
    invalid = (
        flags.select(
            [
                (pl.col(column).is_not_null() & (pl.col(column) != 0) & (pl.col(column) != 1))
                .sum()
                .alias(column)
                for column in FLAG_COLUMNS
            ]
        )
        .sum_horizontal()
        .item()
    )
    return int(nulls), int(invalid)


def critical_failure_stats(df: pl.DataFrame) -> tuple[int, int]:
    """Zwraca (liczba critical failures, liczba klatek ze znakiem)."""
    sign_frames = df.filter(pl.col("actual_class") != 0).height
    critical = int(df["is_critical_failure"].sum())
    return critical, sign_frames


@asset_check(asset=evaluate_metrics)
def check_flag_integrity(evaluate_metrics: pl.DataFrame) -> AssetCheckResult:
    """Flagi KPI muszą być bin­arne (0/1) i pozbawione nulli."""
    nulls, invalid = flag_integrity(evaluate_metrics)
    return AssetCheckResult(
        passed=(nulls == 0 and invalid == 0),
        metadata={"nulls": nulls, "out_of_range": invalid},
    )


@asset_check(asset=evaluate_metrics)
def check_dataset_size(evaluate_metrics: pl.DataFrame) -> AssetCheckResult:
    """Dataset nie może się nagle skurczyć (ochrona przed częściowym ingestem)."""
    rows = evaluate_metrics.height
    return AssetCheckResult(
        passed=rows >= MIN_EXPECTED_ROWS,
        metadata={"rows": rows, "min_expected_rows": MIN_EXPECTED_ROWS},
    )


@asset_check(asset=evaluate_metrics)
def check_critical_failure_rate(evaluate_metrics: pl.DataFrame) -> AssetCheckResult:
    """Odsetek przeoczonych STOP/YIELD w złej pogodzie musi mieścić się w budżecie ryzyka."""
    critical, sign_frames = critical_failure_stats(evaluate_metrics)
    rate = critical / sign_frames if sign_frames else 1.0
    return AssetCheckResult(
        passed=rate < MAX_CRITICAL_FAILURE_RATE,
        metadata={
            "critical_failures": critical,
            "sign_frames": sign_frames,
            "critical_failure_rate": round(rate, 6),
            "max_accepted_rate": MAX_CRITICAL_FAILURE_RATE,
        },
    )
