import pandera as pa
import polars as pl
from pandera.polars import DataFrameModel


class DetectionSchema(DataFrameModel):
    frame_id: pl.Int64
    actual_class: pl.Int64 = pa.Field(isin=[0, 1, 2, 3, 4])
    predicted_class: pl.Int64 = pa.Field(isin=[0, 1, 2, 3, 4])
    confidence: pl.Float64 = pa.Field(ge=0.0, le=1.0)
    bbox_iou: pl.Float64 = pa.Field(ge=0.0, le=1.0)
    weather: pl.Int64 = pa.Field(isin=[0, 1, 2])

    class Config:
        strict = True
