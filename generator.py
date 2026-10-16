import os
import sys
from pathlib import Path

import numpy as np

# Add src to path to import generated proto
sys.path.append(os.path.abspath("src"))
from av_portfolio.proto import traffic_signs_pb2


def generate_mock_data(n=5_000_000, output_path="data/raw/detections.pb"):
    print(f"🚀 Generowanie {n} rekordów Protobuf...")

    # 1. Wektoryzowane generowanie danych za pomocą NumPy
    frame_ids = np.arange(n, dtype=np.int64)
    weather_probs = [0.7, 0.2, 0.1]  # SUNNY, RAIN, FOG
    weathers = np.random.choice([0, 1, 2], n, p=weather_probs)

    # Klasy: NONE=0, STOP=1, YIELD=2, SPEED_LIMIT=3, OTHER=4
    classes = [0, 1, 2, 3, 4]
    actual_classes = np.random.choice(classes, n, p=[0.50, 0.05, 0.05, 0.35, 0.05])

    # Logika błędów: we mgle (weather=2) model częściej zwraca NONE (0) zamiast STOP (1)
    predicted_classes = actual_classes.copy()

    # Znajdź indeksy, gdzie jest mgła i znak STOP
    fog_stop_mask = (weathers == 2) & (actual_classes == 1)
    # Wstrzyknij błąd: 80% szans na NONE zamiast STOP we mgle
    fog_error_indices = np.where(fog_stop_mask)[0]
    error_mask = np.random.random(len(fog_error_indices)) < 0.8
    predicted_classes[fog_error_indices[error_mask]] = 0

    # Inne losowe błędy (5% szans na pomyłkę)
    random_error_mask = np.random.random(n) < 0.05
    predicted_classes[random_error_mask] = np.random.choice(classes, np.sum(random_error_mask))

    confidences = np.random.uniform(0.3, 1.0, n)
    bbox_ious = np.random.uniform(0.5, 0.99, n)

    # 2. Budowanie paczki Protobuf
    batch = traffic_signs_pb2.DetectionBatch()

    print("📦 Serializacja do obiektów Protobuf (to może chwilę potrwać)...")

    # Niestety Protobuf Python nie wspiera wektoryzacji, ale optymalizujemy loop
    # Przyspieszamy używając lokalnych zmiennych i list comprehension jeśli to możliwe
    # Ale dla 5M rekordów standardowy loop jest czytelniejszy.

    detections = []
    for i in range(n):
        det = traffic_signs_pb2.SignDetection(
            frame_id=frame_ids[i],
            actual_class=actual_classes[i],
            predicted_class=predicted_classes[i],
            confidence=float(confidences[i]),
            bbox_iou=float(bbox_ious[i]),
            weather=weathers[i],
        )
        detections.append(det)

    batch.detections.extend(detections)

    # 3. Zapis do pliku
    print(f"💾 Zapisywanie do {output_path}...")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(batch.SerializeToString())

    print(f"✅ Gotowe! Rozmiar pliku: {os.path.getsize(output_path) / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    generate_mock_data()
