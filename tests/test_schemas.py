import polars as pl
import pytest
from pandera.errors import SchemaError

from av_portfolio.models.schemas import DetectionSchema


def _valid_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "frame_id": [1, 2],
            "actual_class": [0, 1],
            "predicted_class": [0, 1],
            "confidence": [0.5, 0.9],
            "bbox_iou": [0.5, 0.8],
            "weather": [0, 2],
        }
    )


def test_valid_frame_passes_and_preserves_data() -> None:
    df = _valid_df()
    out = DetectionSchema.validate(df)
    assert out.equals(df)


@pytest.mark.parametrize(
    ("column", "bad_values"),
    [
        ("actual_class", [5, 1]),  # klasa spoza enum
        ("predicted_class", [-1, 2]),  # klasa spoza enum
        ("confidence", [1.5, 0.2]),  # > 1.0
        ("confidence", [-0.1, 0.2]),  # < 0.0
        ("bbox_iou", [0.5, 1.01]),  # > 1.0
        ("weather", [0, 3]),  # pogoda spoza enum
    ],
)
def test_out_of_range_values_rejected(column: str, bad_values: list[float]) -> None:
    df = _valid_df().with_columns(pl.Series(column, bad_values))

    with pytest.raises(SchemaError):
        DetectionSchema.validate(df)


def test_extra_column_rejected() -> None:
    df = _valid_df().with_columns(pl.Series("unknown", [1, 2]))

    with pytest.raises(SchemaError):
        DetectionSchema.validate(df)


def test_missing_column_rejected() -> None:
    df = _valid_df().drop("weather")

    with pytest.raises(SchemaError):
        DetectionSchema.validate(df)


def test_wrong_dtype_rejected() -> None:
    df = _valid_df().with_columns(pl.Series("frame_id", ["a", "b"]))

    with pytest.raises(SchemaError):
        DetectionSchema.validate(df)
