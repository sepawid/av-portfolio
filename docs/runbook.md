# Runbook — AV Portfolio (TSR KPI Pipeline)

Instrukcja operacyjna: jak uruchomić pipeline lokalnie, gdzie szukać wyników i co robić, gdy coś nie działa.

## Wymagania

- [uv](https://docs.astral.sh/uv/) (zarządzanie zależnościami)
- [Docker + docker compose](https://docs.docker.com/compose/) (tylko dla warstwy BI/Redash)
- Linux/macOS (na Windowsie użyj WSL2)

## 1. Setup środowiska

```bash
uv sync            # tworzy .venv i instaluje zależności (runtime + dev)
```

Weryfikacja:

```bash
uv run python -c "import av_portfolio; print('OK')"
```

## 2. Dane wejściowe

Dane surowe to plik Protobuf `data/raw/detections.pb` (5M rekordów, ~92 MB).
Katalog `data/` jest generowany i **nie jest wersjonowany** w gicie.

Regeneracja danych (~5 sekund, deterministyczna — `SEED=42`):

```bash
uv run python generator.py
```

Po zmianach w `traffic_signs.proto` zregeneruj bindingi Pythona:

```bash
./scripts/generate_proto.sh
```

> Uwaga: `data/outputs/redash_db.sqlite` (raport dla Redash) powstaje dopiero po uruchomieniu pipeline'u.

## 3. Uruchomienie pipeline'u

### Wariant A — jedna komenda (demo)

```bash
uv run python demo_run.py
```

Wykonuje wszystkie assety w kolejności:
`ingest_logs` → `validate_schema` → `evaluate_metrics` → `export_parquet` → `duckdb_bridge`.

### Wariant B — Dagster UI (dev)

```bash
uv run python -m dagster dev
```

UI: [http://localhost:3000](http://localhost:3000) → zakładka Assets → „Materialize all".

## 4. Wyniki (artefakty)

| Plik | Zawartość |
|---|---|
| `data/processed/results.parquet` | 5M wierszy z flagami KPI (TP/FP/FN/critical) |
| `data/outputs/redash_db.sqlite` | Agregat `kpi_report` per pogoda (dla Redash) |

Szybki podgląd z DuckDB:

```bash
uv run python -c "
import duckdb
rows = duckdb.sql(\"SELECT * FROM 'data/outputs/redash_db.sqlite'.kpi_report\").fetchall()
for row in rows:
    print(row)
"
```

## 5. Warstwa BI (Redash)

```bash
docker compose up -d
```

### Automatyzacja (zalecane)

```bash
./scripts/redash_setup.sh      # inicjalizacja bazy + rejestracja datasource SQLite
./scripts/redash_provision.sh  # konto serwisowe + zapisane query + dashboard (REST API)
```

`redash_provision.sh` tworzy (idempotentnie — przy ponownym uruchomieniu zastępuje
stare obiekty):

- konto serwisowe **`demo@av.local` / `av-demo-2026`** (admin na tej lokalnej instancji;
  Twoje własne konto pozostaje nietknięte),
- zapisane query **„KPI per weather"** (wyniki wykonane i zacache'owane),
- wizualizacje (tabela + wykres słupkowy recall) i dashboard **„AV KPI Overview"**:
  [http://localhost:5000/dashboard/av-kpi-overview](http://localhost:5000/dashboard/av-kpi-overview)
  (link po stabilnym slugu; URL-e z `/dashboards/<id>` też działają, ale ID zmienia się
  przy ponownym provisioningu).

### Kroki manualne (alternatywa)

1. `docker compose run --rm server create_db` — jednorazowa inicjalizacja bazy Redasha.
2. Otwórz [http://localhost:5000](http://localhost:5000) i utwórz konto admina.
3. **Settings → Data Sources → New Data Source**:
   - Type: `SQLite`
   - Database Path: `/data/redash_db.sqlite` (katalog `data/outputs` jest zamontowany jako `/data` w kontenerach)
4. Przykładowe zapytanie (uwaga: SQLite w kontenerze Redasha jest stary, bez `NULLS LAST`):

```sql
SELECT * FROM kpi_report ORDER BY weather IS NULL, weather;
```

Po zmianie danych wystarczy odświeżyć zapytanie — plik SQLite jest nadpisywany przez asset `duckdb_bridge`.

## 6. Kontrola jakości

```bash
./scripts/lint.sh    # ruff format + ruff check + mypy (strict) + pytest
```

Konfiguracja CI: `.github/workflows/ci.yml` (te same kroki na GitHub Actions).

## 7. Troubleshooting

| Objaw | Przyczyna | Rozwiązanie |
|---|---|---|
| `FileNotFoundError: data/raw/detections.pb` | brak danych wejściowych | `uv run python generator.py` |
| Błąd parsowania Protobuf / `DecodeError` | bindingi niezgodne z `traffic_signs.proto` | `./scripts/generate_proto.sh`, potem regeneracja danych |
| `IO Error: Extension "sqlite" not found` | DuckDB nie może pobrać rozszerzenia | sprawdź dostęp do sieci (pierwsze uruchomienie pobiera extension) |
| `SchemaError` z Pandery przy `validate_schema` | dane niezgodne ze `DetectionSchema` | sprawdź, czy `.pb` pochodzi z aktualnego `generator.py` / `.proto` |
| Redash nie widzi bazy | brak `create_db` lub błędna ścieżka datasource | wykonaj krok 5; ścieżka musi być `/data/redash_db.sqlite` |
| `av_portfolio` nie importuje się | brak `uv sync` | `uv sync` |

## 8. Alerty (Dagster sensor)

Run, który zakończy się z nieudanym asset checkiem (np. przekroczony budżet
`critical_failures < 5%` lub za mały dataset), jest wyłapywany przez sensor
`quality_gate_alert_sensor` (run status sensor, domyślnie **włączony** —
zakładka *Automation* w UI, patrz `docs/figures/dagster_sensor.png`).

Alert trafia:

1. do logu daemona jako `ERROR` (i do historii ticków sensora w UI),
2. opcjonalnie do webhooka — ustaw `AV_ALERT_WEBHOOK_URL` (POST JSON
   `{"text": ...}`, zgodny ze Slackiem; best-effort, timeout 5 s).

Przykład (run z uciętym datasetem, `n=200_000`):

```text
🚨 AV KPI quality gate failed in run a919b1d1 (1 check(s)):
  • check_dataset_size
See docs/runbook.md -> Alerting.
```

Uwagi:

- sensor działa na wspólnej instancji (`dagster dev`, `dagster asset
  materialize`); runy in-process (`demo_run.py`) są efemeryczne i nie generują
  alertów,
- `monitor_all_code_locations=True` — runy odpalane z CLI nie mają
  `remote_job_origin`, więc domyślny matching per-lokalizacja by je pomijał.

Szybki test end-to-end:

```bash
# 1. mały dataset -> check_dataset_size padnie
uv run python -c "from generator import generate_mock_data; generate_mock_data(n=200_000)"
# 2. run na wspólnej instancji (wymaga uruchomionego `dagster dev` z tym samym DAGSTER_HOME)
DAGSTER_HOME=.tmp_dagster_home uv run python -m dagster asset materialize --select "*" -m av_portfolio.definitions
# 3. w logu daemona po ~30-60 s pojawi się alert ERROR (🚨 ...)
# 4. przywróć pełne dane
uv run python generator.py
```
