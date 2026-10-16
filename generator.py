from dataclasses import dataclass
from pathlib import Path

import numpy as np

from av_portfolio.proto import traffic_signs_pb2
from av_portfolio.utils.paths import RAW_DATA_DIR

SEED = 42


@dataclass(frozen=True)
class ModelProfile:
    """Parametry symulowanego profilu jakości modelu TSR."""

    fog_stop_miss_rate: float
    """Odsetek przeoczeń STOP we mgle (predykcja NONE)."""

    random_error_rate: float
    """Odsetek losowych pomyłek klasy (dowolna pogoda)."""

    correct_conf: tuple[float, float]
    """Zakres confidence dla poprawnych predykcji."""

    error_conf: tuple[float, float]
    """Zakres confidence dla błędnych predykcji."""

    correct_iou: tuple[float, float]
    """Zakres IoU boxa dla poprawnych predykcji."""

    error_iou: tuple[float, float]
    """Zakres IoU boxa dla błędnych predykcji."""


PROFILES: dict[str, ModelProfile] = {
    # Baseline: kiepski na STOP we mgle, słabo skalibrowana pewność.
    "v1": ModelProfile(
        fog_stop_miss_rate=0.8,
        random_error_rate=0.05,
        correct_conf=(0.65, 1.0),
        error_conf=(0.3, 0.8),
        correct_iou=(0.66, 0.99),
        error_iou=(0.4, 0.8),
    ),
    # Ulepszony: lepsza obsługa mgły, mniej błędów, lepsza kalibracja i boxy.
    "v2": ModelProfile(
        fog_stop_miss_rate=0.25,
        random_error_rate=0.03,
        correct_conf=(0.75, 1.0),
        error_conf=(0.3, 0.78),
        correct_iou=(0.68, 0.99),
        error_iou=(0.3, 0.7),
    ),
}


def generate_mock_data(
    n: int = 5_000_000, output_path: Path | None = None, profile: str = "v1"
) -> None:
    """Generuje syntetyczne detekcje TSR (domyślnie 5M rekordów) do pliku Protobuf.

    Dane są deterministyczne (SEED=42 + offset profilu) i celowo zawierają błędy
    krytyczne: przeoczenie STOP we mgle oraz losowe pomyłki — ich natężenie zależy
    od profilu modelu (``v1`` = baseline, ``v2`` = ulepszony).

    Profil confidence jest skalibrowany: poprawne predykcje mają wyższą pewność,
    a błędne niższą — dzięki temu próg decyzyjny modelu (CONFIDENCE_THRESHOLD)
    działa realistycznie. Podobnie IoU bounding boxa: trafienia są lepiej
    zlokalizowane niż pomyłki.
    """
    if profile not in PROFILES:
        raise ValueError(f"Nieznany profil modelu: {profile!r} (dostępne: {sorted(PROFILES)})")
    params = PROFILES[profile]

    if output_path is None:
        name = "detections.pb" if profile == "v1" else f"detections_{profile}.pb"
        output_path = RAW_DATA_DIR / name

    # Offset seeda per profil: v1 zachowuje oryginalny SEED (deterministyczne dane).
    profile_offset = list(PROFILES).index(profile) * 1000
    rng = np.random.default_rng(SEED + profile_offset)
    print(
        f"🚀 Generowanie {n} rekordów Protobuf (profil={profile}, seed={SEED + profile_offset})..."
    )

    # 1. Wektoryzowane generowanie danych za pomocą NumPy
    frame_ids = np.arange(n, dtype=np.int64)
    weather_probs = [0.7, 0.2, 0.1]  # SUNNY, RAIN, FOG
    weathers = rng.choice([0, 1, 2], n, p=weather_probs)

    # Klasy: NONE=0, STOP=1, YIELD=2, SPEED_LIMIT=3, OTHER=4
    classes = [0, 1, 2, 3, 4]
    actual_classes = rng.choice(classes, n, p=[0.50, 0.05, 0.05, 0.35, 0.05])

    # Logika błędów: we mgle (weather=2) model częściej zwraca NONE (0) zamiast STOP (1)
    predicted_classes = actual_classes.copy()

    # Znajdź indeksy, gdzie jest mgła i znak STOP
    fog_stop_mask = (weathers == 2) & (actual_classes == 1)
    # Wstrzyknij błąd zależny od profilu modelu
    fog_error_indices = np.where(fog_stop_mask)[0]
    error_mask = rng.random(len(fog_error_indices)) < params.fog_stop_miss_rate
    predicted_classes[fog_error_indices[error_mask]] = 0

    # Inne losowe błędy
    random_error_mask = rng.random(n) < params.random_error_rate
    predicted_classes[random_error_mask] = rng.choice(classes, np.sum(random_error_mask))

    # Kalibracja pewności: trafienia pewniejsze niż błędy
    is_error = predicted_classes != actual_classes
    confidences = np.where(
        is_error,
        rng.uniform(*params.error_conf, n),
        rng.uniform(*params.correct_conf, n),
    )

    # Kalibracja lokalizacji: trafione detekcje mają wyższy IoU niż pomyłki
    bbox_ious = np.where(
        is_error,
        rng.uniform(*params.error_iou, n),
        rng.uniform(*params.correct_iou, n),
    )

    # 2. Budowanie paczki Protobuf
    batch = traffic_signs_pb2.DetectionBatch()  # type: ignore

    print("📦 Serializacja do obiektów Protobuf (to może chwilę potrwać)...")

    # Protobuf Python nie wspiera wektoryzacji, ale extend() przyjmuje generator,
    # więc nie trzymamy w pamięci dodatkowej listy 5M obiektów.
    batch.detections.extend(
        traffic_signs_pb2.SignDetection(  # type: ignore
            frame_id=frame_ids[i],
            actual_class=actual_classes[i],
            predicted_class=predicted_classes[i],
            confidence=float(confidences[i]),
            bbox_iou=float(bbox_ious[i]),
            weather=weathers[i],
        )
        for i in range(n)
    )

    # 3. Zapis do pliku
    print(f"💾 Zapisywanie do {output_path}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(batch.SerializeToString())

    print(f"✅ Gotowe! Rozmiar pliku: {output_path.stat().st_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    generate_mock_data()
