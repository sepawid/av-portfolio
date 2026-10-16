from pathlib import Path

import numpy as np

from av_portfolio.proto import traffic_signs_pb2
from av_portfolio.utils.paths import RAW_DATA_DIR

SEED = 42


def generate_mock_data(n: int = 5_000_000, output_path: Path | None = None) -> None:
    """Generuje syntetyczne detekcje TSR (domyślnie 5M rekordów) do pliku Protobuf.

    Dane są deterministyczne (SEED=42) i celowo zawierają błędy krytyczne:
    przeoczenie STOP we mgle (80% szans) oraz 5% losowych pomyłek.
    Profil confidence jest skalibrowany: poprawne predykcje mają wyższą pewność
    (0.65-1.0), a błędne niższą (0.3-0.8) — dzięki temu próg decyzyjny modelu
    (CONFIDENCE_THRESHOLD) działa realistycznie.
    """
    if output_path is None:
        output_path = RAW_DATA_DIR / "detections.pb"

    rng = np.random.default_rng(SEED)
    print(f"🚀 Generowanie {n} rekordów Protobuf (seed={SEED})...")

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
    # Wstrzyknij błąd: 80% szans na NONE zamiast STOP we mgle
    fog_error_indices = np.where(fog_stop_mask)[0]
    error_mask = rng.random(len(fog_error_indices)) < 0.8
    predicted_classes[fog_error_indices[error_mask]] = 0

    # Inne losowe błędy (5% szans na pomyłkę)
    random_error_mask = rng.random(n) < 0.05
    predicted_classes[random_error_mask] = rng.choice(classes, np.sum(random_error_mask))

    # Kalibracja pewności: trafienia pewniejsze niż błędy
    is_error = predicted_classes != actual_classes
    confidences = np.where(
        is_error,
        rng.uniform(0.3, 0.8, n),
        rng.uniform(0.65, 1.0, n),
    )
    bbox_ious = rng.uniform(0.5, 0.99, n)

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
