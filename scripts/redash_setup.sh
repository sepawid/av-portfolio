#!/bin/bash
set -e

DATA_SOURCE_NAME="AV KPI (SQLite)"

echo "🐘 Inicjalizacja bazy Redasha (postgres)..."
docker compose run --rm server create_db

echo "🔌 Rejestracja datasource SQLite (AV KPI)..."
# --entrypoint obchodzi quoting w bin/docker-entrypoint (`exec manage.py $*`),
# dzięki czemu nazwa ze spacjami i JSON z opcjami przechodzą nienaruszone.
if docker compose run --rm --entrypoint /app/manage.py server ds delete "$DATA_SOURCE_NAME" > /dev/null 2>&1; then
    echo "   (usunięto istniejący datasource o tej nazwie)"
fi
docker compose run --rm --entrypoint /app/manage.py server ds new "$DATA_SOURCE_NAME" \
    --type sqlite \
    --options '{"dbpath": "/data/redash_db.sqlite"}'

echo "🧪 Test połączenia..."
docker compose run --rm --entrypoint /app/manage.py server ds test "$DATA_SOURCE_NAME"

echo "✅ Gotowe! Otwórz http://localhost:5000 i utwórz konto admina."
echo "   Przykładowe zapytanie: SELECT * FROM kpi_report ORDER BY weather IS NULL, weather;"
