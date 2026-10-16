from dagster import Definitions

from .assets import all_asset_checks, all_assets

defs = Definitions(
    assets=all_assets,
    asset_checks=all_asset_checks,
)
