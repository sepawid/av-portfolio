# Project Plan — AV Portfolio (TSR KPI Pipeline)

Plan rozwoju projektu i jego aktualny status. Zakres: pipeline ewaluacji modelu percepcji AV (rozpoznawanie znaków drogowych) na syntetycznych danych 5M rekordów.

## Cel projektu

Pokazać produkcyjny wzorzec przetwarzania danych dla wizji komputerowej w AV:

- binarny ingest (Protobuf) → wektoryzacja (Polars lazy) → walidacja (Pandera) → KPI → Parquet → DuckDB → BI (Redash),
- orkiestracja assetowa (Dagster) z rejestrem lineage,
- rygorystyczna jakość: mypy strict, ruff, testy, CI.

## Fazy

### Faza 1 — Rdzeń pipeline'u ✅ (zakończona)

- [x] Schemat Protobuf (`traffic_signs.proto`) + generator danych syntetycznych (5M rekordów)
- [x] Assety Dagstera: `ingest_logs`, `validate_schema`, `evaluate_metrics`, `export_parquet`, `duckdb_bridge`
- [x] Walidacja schematu (Pandera) i wektoryzowane KPI (Polars)
- [x] Most DuckDB → SQLite dla Redash

### Faza 2 — Higiena repo i CI ✅ (zakończona)

- [x] `.gitignore` dla danych generowanych, cache'y i artefaktów
- [x] Instalowalny pakiet (`uv_build`) — koniec z hackami `sys.path`/`src.` importami
- [x] Zależności runtime vs dev (`dependency-groups`), usunięcie nieużywanych (pandas, pyarrow)
- [x] CI na GitHub Actions: `ruff format --check`, `ruff check`, `mypy src`, `pytest`
- [x] Skrypty: `scripts/lint.sh` (+pytest), `scripts/generate_proto.sh`

### Faza 3 — Testy i dokumentacja ✅ (zakończona)

- [x] Refaktor pod testowalność: `load_detections()` i `compute_kpi_flags()` jako czyste funkcje
- [x] Testy jednostkowe: flagi KPI (tabela przypadków), schemat Pandery, roundtrip Protobuf
- [x] Dokumentacja: `kpi-definition.md`, `runbook.md`, `project-plan.md` (ten plik)

### Faza 4 — Poprawa semantyki KPI ✅ (zakończona)

- [x] Spójny próg `confidence` dla TP/FP/FN („efektywna predykcja", `CONFIDENCE_THRESHOLD = 0.7`)
- [x] Wyeliminowanie fałszywych TP dla pary NONE/NONE; dodanie flagi `is_true_negative`
- [x] Moduł `domain.py` z enumami + test synchronizacji z `.proto`
- [x] Rozszerzenie raportu SQLite: `precision`, `recall`, `f1` + wiersz zbiorczy (ALL)
- [x] Generator danych: seed (determinizm) + kalibracja confidence (trafienia pewniejsze niż błędy)
- [x] Regeneracja danych wyjściowych i aktualizacja testów; automatyzacja setupu Redash (`scripts/redash_setup.sh`)

### Faza 5 — Prezentacja i portfolio ✅ (zakończona)

- [x] Notebook EDA z realną analizą (recall per klasa × pogoda, sweep progu confidence, critical failures)
- [x] Wykresy (`docs/figures/`) i sekcja „Key Results" w README
- [x] (zrealizowane) porównanie dwóch profili modelu (A/B): `scripts/compare_models.py` + sekcja 7 w notebooku — v2 podnosi recall 0.816 → 0.974 i ścina critical failures o 77%
- [x] (zrealizowane) benchmark wydajności (`scripts/benchmark.py`) + sekcja „Performance" w README (end-to-end ~6 s dla 5M rekordów)
- [x] (zrealizowane) publikacja na GitHub: https://github.com/sepawid/av-portfolio (CI zielone na każdym pushu)

## Definition of Done (każda faza)

1. `./scripts/lint.sh` przechodzi bez błędów (ruff, mypy strict, pytest).
2. Nowe funkcje mają testy jednostkowe.
3. Dokumentacja w `docs/` odzwierciedla stan kodu.
4. Historia git: jeden commit na fazę z opisowym message.
