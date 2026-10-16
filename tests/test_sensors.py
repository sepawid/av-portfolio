"""Tests for the quality-gate alerting sensor (`sensors.py`)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from dagster import AssetCheckEvaluation, AssetCheckSeverity, AssetKey, MetadataValue

from av_portfolio.sensors import (
    FailedCheck,
    build_alert_message,
    failed_checks_from_events,
    send_webhook,
)


def _event(
    check_name: str, passed: bool, metadata: dict[str, Any] | None = None
) -> SimpleNamespace:
    evaluation = AssetCheckEvaluation(
        check_name=check_name,
        asset_key=AssetKey("evaluate_metrics"),
        passed=passed,
        metadata=metadata or {},
        severity=AssetCheckSeverity.ERROR,
    )
    # Mirror the real shape: EventLogEntry.dagster_event.asset_check_evaluation_data
    return SimpleNamespace(dagster_event=SimpleNamespace(asset_check_evaluation_data=evaluation))


def test_failed_checks_from_events_extracts_only_failures() -> None:
    events = [
        _event("check_flag_integrity", passed=True),
        _event(
            "check_critical_failure_rate",
            passed=False,
            metadata={
                "critical_failures": MetadataValue.int(42_611),
                "critical_failure_rate": MetadataValue.float(0.017057),
                "max_accepted_rate": MetadataValue.float(0.05),
            },
        ),
    ]

    failures = failed_checks_from_events(events)

    assert failures == [
        FailedCheck(
            check_name="check_critical_failure_rate",
            critical_failures=42_611,
            rate=0.017057,
            budget=0.05,
        )
    ]


def test_failed_checks_from_events_ignores_foreign_events() -> None:
    events = [SimpleNamespace(dagster_event=None), SimpleNamespace()]

    assert failed_checks_from_events(events) == []


def test_build_alert_message_none_when_all_passed() -> None:
    assert build_alert_message("abcd1234-5678", []) is None


def test_build_alert_message_includes_rate_budget_and_count() -> None:
    message = build_alert_message(
        "abcd1234-5678",
        [
            FailedCheck(
                check_name="check_critical_failure_rate",
                critical_failures=42_611,
                rate=0.0612,
                budget=0.05,
            )
        ],
    )

    assert message is not None
    assert "abcd1234" in message
    assert "check_critical_failure_rate" in message
    assert "6.12%" in message
    assert "budget 5%" in message
    assert "42,611" in message


def test_build_alert_message_without_budget_metadata() -> None:
    message = build_alert_message("abcd1234", [FailedCheck(check_name="check_dataset_size")])

    assert message is not None
    assert "check_dataset_size" in message


def test_send_webhook_without_url_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AV_ALERT_WEBHOOK_URL", raising=False)

    assert send_webhook("hello") is False


def test_send_webhook_unreachable_url_returns_false() -> None:
    assert send_webhook("hello", url="http://127.0.0.1:1/hook") is False
