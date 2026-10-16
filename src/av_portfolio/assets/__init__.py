from dagster import load_assets_from_modules

from . import ingestion, metrics, reporting

all_assets = load_assets_from_modules([ingestion, metrics, reporting])
