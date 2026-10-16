from pathlib import Path

import pytest

from av_portfolio.assets.ingestion import load_detections
from av_portfolio.proto import traffic_signs_pb2


def test_load_detections_roundtrip(tmp_path: Path) -> None:
    batch = traffic_signs_pb2.DetectionBatch()  # type: ignore
    batch.detections.extend(
        [
            traffic_signs_pb2.SignDetection(  # type: ignore
                frame_id=1,
                actual_class=1,
                predicted_class=1,
                confidence=0.9,
                bbox_iou=0.8,
                weather=2,
            ),
            traffic_signs_pb2.SignDetection(  # type: ignore
                frame_id=2,
                actual_class=3,
                predicted_class=0,
                confidence=0.4,
                bbox_iou=0.6,
                weather=0,
            ),
        ]
    )

    pb_file = tmp_path / "mini.pb"
    pb_file.write_bytes(batch.SerializeToString())

    df = load_detections(pb_file)

    assert df.shape == (2, 6)
    assert df.columns == [
        "frame_id",
        "actual_class",
        "predicted_class",
        "confidence",
        "bbox_iou",
        "weather",
    ]
    assert df["frame_id"].to_list() == [1, 2]
    assert df["actual_class"].to_list() == [1, 3]
    assert df["predicted_class"].to_list() == [1, 0]
    assert df["weather"].to_list() == [2, 0]
    # float32 w Protobuf -> porównanie z tolerancją
    assert df["confidence"].to_list() == pytest.approx([0.9, 0.4], abs=1e-6)
    assert df["bbox_iou"].to_list() == pytest.approx([0.8, 0.6], abs=1e-6)


def test_load_detections_empty_batch(tmp_path: Path) -> None:
    pb_file = tmp_path / "empty.pb"
    pb_file.write_bytes(traffic_signs_pb2.DetectionBatch().SerializeToString())  # type: ignore

    df = load_detections(pb_file)

    assert df.shape == (0, 6)
