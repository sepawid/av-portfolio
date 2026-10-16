from dagster import load_asset_checks_from_modules, load_assets_from_modules

from . import checks, ingestion, metrics, reporting

all_assets = load_assets_from_modules([ingestion, metrics, reporting])
all_asset_checks = load_asset_checks_from_modules([checks])
