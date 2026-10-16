#!/bin/bash
set -euo pipefail

# Buduje statyczny raport dla GitHub Pages:
# stronę-kokpit (docs/site/index.html) + notebook jako HTML + figurki.
# Wynik trafia do katalogu `site/` (git-ignored); workflow `.github/workflows/pages.yml`
# publikuje go na GitHub Pages pod https://sepawid.github.io/av-portfolio/

SITE_DIR="site"

rm -rf "$SITE_DIR"
mkdir -p "$SITE_DIR/figures"

cp docs/site/index.html "$SITE_DIR/index.html"
cp docs/figures/*.png "$SITE_DIR/figures/"

uv run jupyter nbconvert \
    --to html \
    --template classic \
    --output-dir "$SITE_DIR" \
    --output notebook.html \
    notebooks/exploration.ipynb

echo "✅ Zbudowano raport: $SITE_DIR/"
