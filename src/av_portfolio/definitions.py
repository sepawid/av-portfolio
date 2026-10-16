from dagster import Definitions

from .assets import all_asset_checks, all_assets
from .sensors import quality_gate_alert_sensor

defs = Definitions(
    assets=all_assets,
    asset_checks=all_asset_checks,
    sensors=[quality_gate_alert_sensor],
)
