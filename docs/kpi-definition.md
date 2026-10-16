# Definicja KPI — Traffic Sign Recognition (TSR)

Dokument opisuje, jak pipeline liczy flagi KPI. Implementacja: `src/av_portfolio/assets/metrics.py` (funkcja `compute_kpi_flags`).

Enumy klas i pogody: `src/av_portfolio/domain.py` — synchronizacja z `traffic_signs.proto` pilnowana testem `tests/test_domain.py`.

## Dane wejściowe

Pojedynczy wiersz = jedna detekcja w klatce (frame):

| Kolumna | Typ | Zakres | Opis |
|---|---|---|---|
| `frame_id` | int | >= 0 | Identyfikator klatki |
| `actual_class` | enum | 0–4 | Znak faktycznie obecny (ground truth) |
| `predicted_class` | enum | 0–4 | Predykcja modelu |
| `confidence` | float | 0.0–1.0 | Pewność predykcji |
| `bbox_iou` | float | 0.0–1.0 | IoU bounding boxa (nieużywane w flagach) |
| `weather` | enum | 0–2 | Warunki atmosferyczne |

### Enumy

**SignClass** (`traffic_signs.proto`):

- `0` NONE — brak znaku
- `1` STOP
- `2` YIELD
- `3` SPEED_LIMIT
- `4` OTHER

**Weather**:

- `0` SUNNY, `1` RAIN, `2` FOG

## Efektywna predykcja (próg confidence)

Model uznajemy za „widzący" znak tylko wtedy, gdy `confidence >= CONFIDENCE_THRESHOLD` (domyślnie `0.7`, stała w `metrics.py`). Predykcja z niższą pewnością jest odrzucana i traktowana jak brak detekcji (`NONE`):

```
effective = predicted_class   jeśli confidence >= 0.7
effective = NONE              w przeciwnym przypadku
```

## Flagi KPI

### is_true_positive (TP)

```
actual != NONE AND effective == actual
```

### is_true_negative (TN)

```
actual == NONE AND effective == NONE
```

Poprawna cisza: model nic nie wykrył tam, gdzie nic nie było.

### is_false_positive (FP)

```
effective != NONE AND effective != actual
```

Phantom detection (znak przewidziany bez podstawy) albo błędna klasa znaku.

### is_false_negative (FN)

```
actual != NONE AND effective != actual
```

Przeoczenie znaku — brak predykcji, błędna klasa **lub** pewność poniżej progu.

### is_critical_failure

```
actual IN {STOP, YIELD} AND effective != actual AND weather != SUNNY
```

Najgroźniejsza klasa błędu: efektywne przeoczenie STOP/YIELD w deszczu lub mgle.

### Uwagi projektowe

- Błędna klasyfikacja znaku (`actual` i `effective` to różne klasy nie-NONE) zapala **jednocześnie FP i FN** — świadoma konwencja prostego modelu flagowego (nie jest to macierz pomyłek).
- Predykcja poprawna klasowo, ale z pewnością poniżej progu, liczy się jako FN (model „nie podjął decyzji") — dlatego próg confidence należy traktować jako część definicji modelu.
- Ten sam próg obowiązuje TP, FP, FN i critical failures (spójność).

## Agregacja i raportowanie

`duckdb_bridge` (`src/av_portfolio/assets/reporting.py`) buduje tabelę `kpi_report` w `data/outputs/redash_db.sqlite` (Redash):

| Kolumna | Opis |
|---|---|
| `weather_label`, `weather` | SUNNY / RAIN / FOG oraz wiersz zbiorczy `ALL` (`weather IS NULL`, z GROUPING SETS) |
| `total_frames` | liczba klatek w segmencie |
| `tp`, `tn`, `fp`, `fn` | sumy flag |
| `critical_failures` | suma `is_critical_failure` |
| `precision` | `tp / (tp + fp)` (NULL-safe) |
| `recall` | `tp / (tp + fn)` (NULL-safe) |
| `f1` | `2*tp / (2*tp + fp + fn)` (NULL-safe) |
