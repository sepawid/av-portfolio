#!/bin/bash
set -e

echo "🐘 Inicjalizacja bazy Redasha (postgres)..."
docker-compose run --rm server create_db

echo "🔌 Rejestracja datasource SQLite (AV KPI)..."
docker-compose run --rm server manage ds new "AV KPI (SQLite)" \
    --type sqlite \
    --options '{"dbpath": "/data/redash_db.sqlite"}'

echo "✅ Gotowe! Otwórz http://localhost:5000 i utwórz konto admina."
echo "   Przykładowe zapytanie: SELECT * FROM kpi_report ORDER BY weather NULLS LAST;"
