import polars as pl
from dagster import AssetExecutionContext, asset

from av_portfolio.proto import traffic_signs_pb2
from av_portfolio.utils.paths import RAW_DATA_DIR

RAW_DATA_FILE = RAW_DATA_DIR / "detections.pb"


@asset
def ingest_logs(context: AssetExecutionContext) -> pl.DataFrame:
    """Parsuje plik .pb i rzutuje go do polars.DataFrame."""
    context.log.info(f"Wczytywanie danych z {RAW_DATA_FILE}...")

    batch = traffic_signs_pb2.DetectionBatch()  # type: ignore
    with open(RAW_DATA_FILE, "rb") as f:
        batch.ParseFromString(f.read())

    # Wykorzystujemy list comprehension dla szybkości (Polars świetnie radzi sobie z listami)
    # Dla optymalizacji pamięciowej moglibyśmy użyć generatora, ale Polars
    # potrzebuje długości do optymalnej alokacji

    data = [
        {
            "frame_id": d.frame_id,
            "actual_class": d.actual_class,
            "predicted_class": d.predicted_class,
            "confidence": d.confidence,
            "bbox_iou": d.bbox_iou,
            "weather": d.weather,
        }
        for d in batch.detections
    ]

    df = pl.DataFrame(data)
    context.log.info(f"Zaimportowano {len(df)} rekordów.")
    return df
