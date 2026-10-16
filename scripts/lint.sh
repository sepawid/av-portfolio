#!/bin/bash
set -e

echo "🔍 Running Ruff (Formatting & Linting)..."
uv run ruff format .
uv run ruff check . --fix

echo "🛡️ Running Mypy (Type Checking)..."
PYTHONPATH=src uv run mypy src

echo "🧪 Running Pytest..."
uv run pytest -q

echo "✨ All checks passed!"
