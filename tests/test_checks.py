import polars as pl

from av_portfolio.assets.checks import critical_failure_stats, flag_integrity


def _flags(**overrides: object) -> pl.DataFrame:
    base = {
        "is_true_positive": [0, 1],
        "is_true_negative": [1, 0],
        "is_false_positive": [0, 0],
        "is_false_negative": [1, 0],
        "is_critical_failure": [0, 0],
    }
    base.update(overrides)
    return pl.DataFrame(base)


def test_flag_integrity_clean_frame() -> None:
    nulls, invalid = flag_integrity(_flags())
    assert (nulls, invalid) == (0, 0)


def test_flag_integrity_detects_nulls() -> None:
    df = _flags().with_columns(pl.Series("is_true_positive", [0, None]))
    nulls, invalid = flag_integrity(df)
    assert (nulls, invalid) == (1, 0)


def test_flag_integrity_detects_out_of_range() -> None:
    df = _flags().with_columns(pl.Series("is_critical_failure", [2, 0]))
    nulls, invalid = flag_integrity(df)
    assert (nulls, invalid) == (0, 1)


def test_critical_failure_stats() -> None:
    df = pl.DataFrame(
        {
            "actual_class": [0, 1, 2, 0],
            "is_critical_failure": [0, 1, 1, 0],
        }
    )
    critical, sign_frames = critical_failure_stats(df)
    assert (critical, sign_frames) == (2, 2)
