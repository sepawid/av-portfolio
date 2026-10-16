# Definicja KPI — Traffic Sign Recognition (TSR)

Dokument opisuje, jak pipeline liczy flagi KPI. Implementacja: `src/av_portfolio/assets/metrics.py` (funkcja `compute_kpi_flags`).

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

## Flagi KPI (aktualna implementacja)

### is_true_positive (TP)

```
predicted_class == actual_class AND confidence > 0.7
```

Próg pewności jest **ostry** — przy `confidence == 0.7` flaga się NIE zapala.

### is_false_positive (FP)

```
predicted_class != actual_class AND predicted_class != NONE
```

Predykcja znaku, którego nie ma, albo błędna klasa znaku.

### is_false_negative (FN)

```
predicted_class != actual_class AND actual_class != NONE
```

Przeoczenie istniejącego znaku (brak predykcji lub błędna klasa).

Uwaga: błędna klasyfikacja znaku (`actual != NONE`, `predicted != NONE`, klasy różne) zapala **jednocześnie FP i FN** — to świadoma konwencja tego prostego modelu flagowego.

### is_critical_failure

```
actual_class IN {STOP, YIELD} AND predicted_class != actual_class AND weather != SUNNY
```

Najgroźniejsza klasa błędu: przeoczenie STOP/YIELD w deszczu lub mgle.

## Agregacja i raportowanie

`duckdb_bridge` (`src/av_portfolio/assets/reporting.py`) agreguje dane per pogoda:

- `total_frames`, `tp`, `fp`, `fn`, `critical_failures`

i zapisuje wynik do tabeli `kpi_report` w `data/outputs/redash_db.sqlite` (Redash).

## Znane ograniczenia (do naprawy w kolejnym kroku)

Zidentyfikowane na etapie porządkowania repo — plan naprawy: etap C (`docs/project-plan.md`):

1. **TP bez warunku `actual_class != NONE`** — przypadek „brak znaku i brak predykcji" (NONE/NONE) obecnie zapala flagę TP, sztucznie zawyżając wynik. Przy rozkładzie danych, gdzie ~50% to NONE, to poważne zniekształcenie.
2. **Próg confidence stosowany tylko w TP** — FP i FN ignorują pewność predykcji, więc predykcja z `confidence = 0.05` liczy się tak samo jak z `0.99`.
3. **Magiczne liczby** — `[1, 2]`, `0`, `0.7` zakodowane wprost w wyrażeniach, zamiast odwołania do enumów z `traffic_signs.proto`.
4. **Brak metryk pochodnych w raporcie** — SQLite zawiera tylko surowe liczniki (tp/fp/fn), bez `precision`/`recall`/`f1`.
