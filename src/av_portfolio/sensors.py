"""Alertowanie: nieudane asset checki (przekroczony budżet KPI) podnoszą alert.

Budżet egzekwuje asset check (`checks.check_critical_failure_rate`), a ten sensor
zamienia zakończony run z nieudanymi checkami w alert operatorski: ERROR w logach
oraz — gdy ustawiono `AV_ALERT_WEBHOOK_URL` — POST JSON (payload zgodny ze Slackiem).

Sensor działa na wspólnej instancji Dagstera (`dagster dev` / `dagster asset
materialize`); runy in-process (`demo_run.py`) są efemeryczne i nie generują alertów.
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from dagster import (
    DagsterEventType,
    DagsterRunStatus,
    DefaultSensorStatus,
    RunStatusSensorContext,
    run_status_sensor,
)

WEBHOOK_ENV_VAR = "AV_ALERT_WEBHOOK_URL"


@dataclass(frozen=True)
class FailedCheck:
    """Podsumowanie nieudanego asset checka wyciągnięte ze zdarzeń runu."""

    check_name: str
    critical_failures: int | None = None
    rate: float | None = None
    budget: float | None = None


def _metadata_value(metadata: dict[str, Any], key: str) -> Any:
    value = metadata.get(key)
    return getattr(value, "value", None)


def failed_checks_from_events(events: Sequence[Any]) -> list[FailedCheck]:
    """Wyciąga nieudane asset checki z listy zdarzeń ASSET_CHECK_EVALUATION."""
    failures: list[FailedCheck] = []
    for event in events:
        dagster_event = getattr(event, "dagster_event", None)
        evaluation = getattr(dagster_event, "asset_check_evaluation_data", None)
        if evaluation is None or evaluation.passed:
            continue
        metadata = evaluation.metadata or {}
        failures.append(
            FailedCheck(
                check_name=evaluation.check_name,
                critical_failures=_metadata_value(metadata, "critical_failures"),
                rate=_metadata_value(metadata, "critical_failure_rate"),
                budget=_metadata_value(metadata, "max_accepted_rate"),
            )
        )
    return failures


def build_alert_message(run_id: str, failures: list[FailedCheck]) -> str | None:
    """Buduje treść alertu; zwraca None, gdy nie ma nieudanych checków."""
    if not failures:
        return None
    lines = [f"🚨 AV KPI quality gate failed in run {run_id[:8]} ({len(failures)} check(s)):"]
    for failure in failures:
        detail = ""
        if failure.rate is not None and failure.budget is not None:
            detail = (
                f": critical failure rate {failure.rate:.2%} exceeds budget {failure.budget:.0%}"
            )
            if failure.critical_failures is not None:
                detail += f" ({failure.critical_failures:,} missed STOP/YIELD)"
        lines.append(f"  • {failure.check_name}{detail}")
    lines.append("See docs/runbook.md -> Alerting.")
    return "\n".join(lines)


def send_webhook(message: str, url: str | None = None) -> bool:
    """Best-effort POST JSON; False, gdy brak URL (env) lub wysyłka się nie udała."""
    url = url or os.environ.get(WEBHOOK_ENV_VAR)
    if not url:
        return False
    request = urllib.request.Request(
        url,
        data=json.dumps({"text": message}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5):
            return True
    except OSError:
        return False


@run_status_sensor(
    run_status=DagsterRunStatus.SUCCESS,
    default_status=DefaultSensorStatus.RUNNING,
    # Runy odpalane z CLI (`dagster asset materialize`) nie mają remote_job_origin,
    # więc domyślny matching per-lokalizacja by je pomijał. Sensor monitoruje całą
    # instancję (pojedynczy projekt = brak ryzyka kolizji z innymi lokalizacjami).
    monitor_all_code_locations=True,
)
def quality_gate_alert_sensor(context: RunStatusSensorContext) -> None:
    """Alertuje, gdy zakończony run ma nieudane asset checki (np. budżet critical failures)."""
    events = context.instance.all_logs(
        context.dagster_run.run_id, of_type=DagsterEventType.ASSET_CHECK_EVALUATION
    )
    message = build_alert_message(context.dagster_run.run_id, failed_checks_from_events(events))
    if message is None:
        context.log.debug("All asset checks passed - no alert.")
        return
    context.log.error(message)
    if send_webhook(message):
        context.log.info("Alert webhook sent.")
