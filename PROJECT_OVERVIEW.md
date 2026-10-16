# AV Portfolio: Architecture-to-File Mapping

Ten dokument wyjaśnia, gdzie dokładnie znajdują się procesy wspomniane w przeglądzie architektury.

## 1. Warstwa Definicji Danych (Data Definition)
*   **Schemat Binarny**: [traffic_signs.proto](file:///home/sebastian/repos/automotive_kpis/av-portfolio/traffic_signs.proto)
    *   *Co tu jest?* Definicja wiadomości `SignDetection` i `DetectionBatch` oraz enumy klas znaków i pogody.
*   **Wygenerowany Kod**: `src/av_portfolio/proto/traffic_signs_pb2.py`
    *   *Co tu jest?* Klasy Pythona wygenerowane z pliku `.proto`, używane do serializacji/deserializacji.

## 1.5. Symulacja i Generowanie Danych (Data Generation Logic)
*   **Logika Generatora**: [generator.py](file:///home/sebastian/repos/automotive_kpis/av-portfolio/generator.py)
    *   *Co tu jest?* Wektorowe generowanie 5 milionów rekordów przy użyciu NumPy.
    *   *Zasada działania:* Implementuje rozkład prawdopodobieństwa klas i **celowo wstrzykuje błędy krytyczne** (np. przeoczenie znaku STOP we mgle), aby przetestować odporność systemu.
*   **Wynikowy plik binarny**: `data/raw/detections.pb`
    *   *Co tu jest?* Skompresowany, binarny plik Protobuf będący punktem wejścia dla całego pipeline'u.

## 2. Inżynieria Danych i Pipeline (Dagster & Polars)
Wszystkie procesy przetwarzania znajdują się w katalogu `src/av_portfolio/assets/`.

*   **Enumy domenowe**: [domain.py](file:///home/sebastian/repos/automotive_kpis/av-portfolio/src/av_portfolio/domain.py)
    *   *Co tu jest?* `IntEnum` dla klas znaków i pogody; spójność z `traffic_signs.proto` wymusza test `tests/test_domain.py`.
*   **Ingest (Protobuf -> Polars)**: [ingestion.py](file:///home/sebastian/repos/automotive_kpis/av-portfolio/src/av_portfolio/assets/ingestion.py)
    *   *Kluczowy proces:* Funkcja `ingest_logs`. Czyta plik `data/raw/detections.pb` i parsuje go do DataFrame.
*   **Walidacja (Pandera)**: [metrics.py](file:///home/sebastian/repos/automotive_kpis/av-portfolio/src/av_portfolio/assets/metrics.py) oraz [schemas.py](file:///home/sebastian/repos/automotive_kpis/av-portfolio/src/av_portfolio/models/schemas.py)
    *   *Kluczowy proces:* Asset `validate_schema`. Wymusza rygorystyczne typowanie przed obliczeniami.
*   **Obliczenia KPI (Polars Lazy)**: [metrics.py](file:///home/sebastian/repos/automotive_kpis/av-portfolio/src/av_portfolio/assets/metrics.py)
    *   *Kluczowy proces:* Asset `evaluate_metrics`. Tutaj znajduje się wektorowa logika `pl.when().then()` wyliczająca TP/TN/FP/FN, Critical Failures oraz poor localization (jakość boxów).
*   **Export do Data Lake**: [reporting.py](file:///home/sebastian/repos/automotive_kpis/av-portfolio/src/av_portfolio/assets/reporting.py)
    *   *Kluczowy proces:* Asset `export_parquet`. Zapisuje wyniki do `data/processed/results.parquet`.

## 3. Analityka i Serwowanie (DuckDB & Redash)
*   **Most Analityczny**: [reporting.py](file:///home/sebastian/repos/automotive_kpis/av-portfolio/src/av_portfolio/assets/reporting.py)
    *   *Kluczowy proces:* Asset `duckdb_bridge`. Agreguje dane za pomocą SQL w DuckDB i wypycha je do `data/outputs/redash_db.sqlite`.
*   **Infrastruktura BI**: [docker-compose.yml](file:///home/sebastian/repos/automotive_kpis/av-portfolio/docker-compose.yml)
    *   *Co tu jest?* Konfiguracja Redasha, Redisa i Postgresa. Montuje wolumen `/data`, aby Redash widział plik SQLite.

## 4. Zarządzanie i Jakość (Quality Assurance)
*   **Konfiguracja Narzędzi**: [pyproject.toml](file:///home/sebastian/repos/automotive_kpis/av-portfolio/pyproject.toml)
    *   *Co tu jest?* Ustawienia dla Ruff (linting) i Mypy (strict typing).
*   **Automatyzacja Kontroli**: [scripts/lint.sh](file:///home/sebastian/repos/automotive_kpis/av-portfolio/scripts/lint.sh)
    *   *Co tu jest?* Skrypt wywołujący `ruff` i `mypy` po kolei.
*   **Testy jednostkowe**: `tests/`
    *   *Co tu jest?* Flag KPI (tabela przypadków TP/TN/FP/FN/critical), walidacja schematu Pandery, roundtrip Protobuf, spójność enumów z `.proto`.

## 5. Dane (Filesystem)
*   `data/raw/detections.pb`: Surowe dane binarne (5M rekordów).
*   `data/processed/results.parquet`: Przetworzone dane z wyliczonymi flagami KPI.
*   `data/outputs/redash_db.sqlite`: Zagregowane wyniki gotowe do wyświetlenia na dashboardzie.
