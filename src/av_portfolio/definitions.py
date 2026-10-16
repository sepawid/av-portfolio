from dagster import Definitions

from .assets import all_assets

defs = Definitions(
    assets=all_assets,
)
