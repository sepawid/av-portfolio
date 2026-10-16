#!/bin/bash
set -euo pipefail

# Pełny provisioning treści w Redashu przez REST API (idempotentny):
# konto serwisowe → login (sesja + CSRF) → zapisane query → wykonanie (job)
# → wizualizacje → dashboard z widgetami.
#
# Wymagania: `docker compose up -d` oraz uruchomiony wcześniej
# `./scripts/redash_setup.sh` (tworzy datasource SQLite).

BASE_URL="http://localhost:5000"
SERVICE_EMAIL="demo@av.local"
SERVICE_PASSWORD="av-demo-2026"
DATA_SOURCE_NAME="AV KPI (SQLite)"
QUERY_NAME="KPI per weather"
DASHBOARD_NAME="AV KPI Overview"

JAR=$(mktemp)
LOGIN_HTML=$(mktemp)
trap 'rm -f "$JAR" "$LOGIN_HTML"' EXIT

log() { echo "▶️  $1"; }
fail() {
    echo "❌ $1" >&2
    exit 1
}

# --- 1. Preflight ------------------------------------------------------------
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/login" || true)
[ "$HTTP_CODE" = "200" ] || fail "Redash nie odpowiada na $BASE_URL — uruchom 'docker compose up -d'."

# --- 2. Konto serwisowe ------------------------------------------------------
# Osobne konto do automatyzacji; Twoje własne konto admina pozostaje nietknięte.
log "Konto serwisowe $SERVICE_EMAIL..."
# Uwaga: celowo nie używamy `... | grep -q` — grep -q zamyka potok, docker
# compose dostaje SIGPIPE i z `set -o pipefail` warunek wyszedłby fałszywie.
EXISTING_USERS=$(docker compose run --rm --entrypoint /app/manage.py server users list 2>/dev/null || true)
if grep -q "$SERVICE_EMAIL" <<<"$EXISTING_USERS"; then
    echo "   (już istnieje — resetuję hasło)"
    docker compose run --rm --entrypoint /app/manage.py server users password "$SERVICE_EMAIL" "$SERVICE_PASSWORD" >/dev/null 2>&1
else
    docker compose run --rm --entrypoint /app/manage.py server users create "$SERVICE_EMAIL" "AV Portfolio Demo" \
        --password "$SERVICE_PASSWORD" --admin >/dev/null 2>&1
fi

# --- 3. Login (sesja + token CSRF) -------------------------------------------
log "Logowanie przez HTTP..."
curl -s -c "$JAR" "$BASE_URL/login" -o "$LOGIN_HTML"
CSRF=$(grep -o 'csrf_token" value="[^"]*"' "$LOGIN_HTML" | sed 's/.*value="//;s/"$//')
curl -s -b "$JAR" -c "$JAR" -X POST "$BASE_URL/login" \
    --data-urlencode "csrf_token=$CSRF" \
    --data-urlencode "email=$SERVICE_EMAIL" \
    --data-urlencode "password=$SERVICE_PASSWORD" \
    -o /dev/null

api() { # api METODA ŚCIEŻKA [JSON]
    local method="$1" path="$2" data="${3:-}"
    if [ -n "$data" ]; then
        curl -s -b "$JAR" -X "$method" "$BASE_URL$path" \
            -H "Content-Type: application/json" -H "X-CSRF-Token: $CSRF" -d "$data"
    else
        curl -s -b "$JAR" -X "$method" "$BASE_URL$path"
    fi
}

SIGNED_IN=$(api GET /api/session | jq -r '.user.email // empty')
[ "$SIGNED_IN" = "$SERVICE_EMAIL" ] || fail "Logowanie nie powiodło się."

# --- 4. Datasource + czyszczenie starych obiektów (idempotencja) -------------
DS_ID=$(api GET /api/data_sources | jq -r --arg n "$DATA_SOURCE_NAME" '.[] | select(.name == $n) | .id')
[ -n "$DS_ID" ] || fail "Brak datasource '$DATA_SOURCE_NAME' — uruchom najpierw ./scripts/redash_setup.sh."

QUERY_URL=$(jq -rn --arg s "$QUERY_NAME" '$s | @uri')
for id in $(api GET "/api/queries?q=$QUERY_URL" | jq -r --arg n "$QUERY_NAME" '.results[] | select(.name == $n) | .id'); do
    log "Usuwam stare query #$id..."
    api DELETE "/api/queries/$id" >/dev/null
done

DASHBOARD_URL=$(jq -rn --arg s "$DASHBOARD_NAME" '$s | @uri')
for id in $(api GET "/api/dashboards?q=$DASHBOARD_URL" | jq -r --arg n "$DASHBOARD_NAME" '.results[] | select(.name == $n) | .id'); do
    log "Usuwam stary dashboard #$id..."
    api DELETE "/api/dashboards/$id" >/dev/null
done

# --- 5. Zapisane query + wykonanie -------------------------------------------
log "Tworzę query '$QUERY_NAME'..."
SQL="SELECT weather_label, precision, recall, f1, critical_failures
FROM kpi_report
ORDER BY weather IS NULL, weather"
QUERY=$(api POST /api/queries "$(jq -n --arg n "$QUERY_NAME" --arg q "$SQL" --argjson ds "$DS_ID" \
    '{name: $n, data_source_id: $ds, query: $q, options: {parameters: []}}')")
QUERY_ID=$(echo "$QUERY" | jq -r '.id')
TABLE_VIZ_ID=$(echo "$QUERY" | jq -r '.visualizations[0].id')

log "Wykonuję query (job)..."
JOB_ID=$(api POST "/api/queries/$QUERY_ID/results" '{"parameters": {}, "max_age": 0}' | jq -r '.job.id')
STATUS=""
for _ in $(seq 1 30); do
    sleep 1
    STATUS=$(api GET "/api/jobs/$JOB_ID" | jq -r '.job.status')
    [ "$STATUS" = "3" ] && break
    [ "$STATUS" = "4" ] && fail "Query zakończyło się błędem: $(api GET "/api/jobs/$JOB_ID" | jq -r '.job.error')"
done
[ "$STATUS" = "3" ] || fail "Timeout wykonania query."

log "Publikuję query (zdejmuję draft)..."
api POST "/api/queries/$QUERY_ID" '{"is_draft": false}' >/dev/null

# --- 6. Wizualizacja wykresu -------------------------------------------------
log "Tworzę wykres słupkowy..."
CHART_OPTS='{"globalSeriesType":"column","sortX":true,"legend":{"enabled":true},
"xAxis":{"type":"category","labels":{"enabled":true}},
"yAxis":[{"type":"linear","rangemode":"tozero"}],"series":{"stacking":null},
"columnMapping":{"weather_label":"x","recall":"y"},"showDataLabels":true}'
CHART_VIZ_ID=$(api POST /api/visualizations "$(jq -n --argjson qid "$QUERY_ID" --argjson o "$CHART_OPTS" \
    '{query_id: $qid, name: "Recall by weather", type: "CHART", options: $o}')" | jq -r '.id')

# --- 7. Dashboard + widgety --------------------------------------------------
log "Tworzę dashboard '$DASHBOARD_NAME'..."
DASHBOARD=$(api POST /api/dashboards "$(jq -n --arg n "$DASHBOARD_NAME" '{name: $n}')")
DASHBOARD_ID=$(echo "$DASHBOARD" | jq -r '.id')
DASHBOARD_SLUG=$(echo "$DASHBOARD" | jq -r '.slug')

TEXT="# AV Perception KPI — TSR benchmark

**Synthetic 5M-frame evaluation** (deterministic generator, seed 42).

- Precision **0.9832** · Recall **0.8163** · F1 **0.8920**
- **42,611 critical failures** (missed STOP/YIELD in rain/fog) — zero in sunny weather
- Fog collapses STOP recall to **0.175** vs ~0.82 in sunny weather"

log "Dodaję widgety (tekst + wykres + tabela)..."
# Uwaga: API wymaga klucza visualization_id nawet dla widgetu tekstowego (null).
api POST /api/widgets "$(jq -n --argjson d "$DASHBOARD_ID" --arg t "$TEXT" \
    '{dashboard_id: $d, visualization_id: null, text: $t, width: 1,
      options: {position: {autoHeight: false, sizeX: 6, sizeY: 2, col: 0, row: 0}}}')" >/dev/null
api POST /api/widgets "$(jq -n --argjson d "$DASHBOARD_ID" --argjson v "$CHART_VIZ_ID" \
    '{dashboard_id: $d, visualization_id: $v, width: 1,
      options: {position: {autoHeight: false, sizeX: 3, sizeY: 4, col: 0, row: 2}}}')" >/dev/null
api POST /api/widgets "$(jq -n --argjson d "$DASHBOARD_ID" --argjson v "$TABLE_VIZ_ID" \
    '{dashboard_id: $d, visualization_id: $v, width: 1,
      options: {position: {autoHeight: false, sizeX: 3, sizeY: 4, col: 3, row: 2}}}')" >/dev/null

# --- 8. Podsumowanie ---------------------------------------------------------
echo
echo "✅ Gotowe!"
echo "   Dashboard: $BASE_URL/dashboards/$DASHBOARD_SLUG"
echo "   Login:     $SERVICE_EMAIL / $SERVICE_PASSWORD"
