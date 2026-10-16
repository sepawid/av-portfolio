import polars as pl
import pytest

from av_portfolio.assets.metrics import compute_kpi_flags


def _one_row(actual: int, predicted: int, confidence: float, weather: int = 0) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "frame_id": [1],
            "actual_class": [actual],
            "predicted_class": [predicted],
            "confidence": [confidence],
            "bbox_iou": [0.8],
            "weather": [weather],
        }
    )


@pytest.mark.parametrize(
    ("actual", "predicted", "confidence", "weather", "tp", "tn", "fp", "fn", "critical"),
    [
        # Klasy: NONE=0, STOP=1, YIELD=2, SPEED_LIMIT=3; pogoda: SUNNY=0, RAIN=1, FOG=2
        # Predykcje z confidence >= 0.7 są "efektywne", poniżej progu odrzucane.
        (1, 1, 0.9, 0, 1, 0, 0, 0, 0),  # trafiony STOP
        (1, 1, 0.7, 0, 1, 0, 0, 0, 0),  # próg włącznie: confidence >= 0.7
        (1, 1, 0.69, 0, 0, 0, 0, 1, 0),  # poprawna predykcja, ale poniżej progu -> przeoczenie (FN)
        (1, 0, 0.9, 0, 0, 0, 0, 1, 0),  # przeoczony STOP, dobra pogoda
        (1, 0, 0.9, 2, 0, 0, 0, 1, 1),  # przeoczony STOP we mgle -> critical
        (2, 0, 0.5, 1, 0, 0, 0, 1, 1),  # przeoczony YIELD w deszczu -> critical
        (3, 0, 0.9, 2, 0, 0, 0, 1, 0),  # przeoczony SPEED_LIMIT we mgle -> nie-critical
        (0, 3, 0.9, 0, 0, 0, 1, 0, 0),  # predykcja znaku, którego nie ma -> FP
        (0, 3, 0.5, 0, 0, 1, 0, 0, 0),  # phantom odrzucony przez próg -> poprawna cisza (TN)
        (0, 0, 0.9, 0, 0, 1, 0, 0, 0),  # brak znaku i brak predykcji -> TN (nie TP!)
        (0, 0, 0.3, 2, 0, 1, 0, 0, 0),  # cisza we mgle -> TN
        (1, 3, 0.9, 0, 0, 0, 1, 1, 0),  # błędna klasyfikacja: FP + FN
        (1, 3, 0.9, 2, 0, 0, 1, 1, 1),  # błędna klasyfikacja STOP we mgle -> critical
        (
            1,
            1,
            0.3,
            2,
            0,
            0,
            0,
            1,
            1,
        ),  # STOP potwierdzony, ale z niską pewnością we mgle -> critical
    ],
)
def test_compute_kpi_flags(
    actual: int,
    predicted: int,
    confidence: float,
    weather: int,
    tp: int,
    tn: int,
    fp: int,
    fn: int,
    critical: int,
) -> None:
    out = compute_kpi_flags(_one_row(actual, predicted, confidence, weather))

    assert out["is_true_positive"].item() == tp
    assert out["is_true_negative"].item() == tn
    assert out["is_false_positive"].item() == fp
    assert out["is_false_negative"].item() == fn
    assert out["is_critical_failure"].item() == critical


def test_compute_kpi_flags_preserves_input_columns() -> None:
    df = _one_row(1, 1, 0.9)
    out = compute_kpi_flags(df)

    flag_columns = {
        "is_true_positive",
        "is_true_negative",
        "is_false_positive",
        "is_false_negative",
        "is_critical_failure",
    }
    assert set(out.columns) == set(df.columns) | flag_columns
    assert out.select(df.columns).equals(df)
