#!/usr/bin/env python
"""A/B harness: porównanie profili modelu (v1 baseline vs v2 ulepszony).

Generuje brakujące datasety (``data/raw/detections_<profil>.pb``), liczy flagi KPI
dokładnie tą samą logiką co pipeline (czyste funkcje z ``av_portfolio``) i zapisuje
tabelę porównawczą do ``data/processed/model_comparison.parquet``.
Wykres i narrację prezentuje notebook ``notebooks/exploration.ipynb`` (sekcja 7).

Uruchamianie (z katalogu repo):

    uv run python scripts/compare_models.py
"""

import sys
from pathlib import Path

import polars as pl

from av_portfolio.assets.ingestion import load_detections
from av_portfolio.assets.metrics import compute_kpi_flags
from av_portfolio.utils.paths import PROCESSED_DATA_DIR, RAW_DATA_DIR

REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILES = ("v1", "v2")


def ensure_dataset(profile: str, n: int) -> Path:
    """Zwraca ścieżkę do datasetu profilu, generując go w razie potrzeby."""
    path = RAW_DATA_DIR / ("detections.pb" if profile == "v1" else f"detections_{profile}.pb")
    if not path.exists():
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from generator import generate_mock_data

        generate_mock_data(n=n, output_path=path, profile=profile)
    return path


def summarize(flags: pl.DataFrame, model: str) -> pl.DataFrame:
    """Agreguje flagi KPI per pogoda + wiersz zbiorczy (weather = NULL)."""
    aggregations = [
        pl.len().alias("frames"),
        pl.col("is_true_positive").sum().alias("tp"),
        pl.col("is_false_positive").sum().alias("fp"),
        pl.col("is_false_negative").sum().alias("fn"),
        pl.col("is_critical_failure").sum().alias("critical_failures"),
        pl.col("is_poor_localization").sum().alias("poor_localizations"),
    ]

    per_weather = flags.group_by("weather").agg(aggregations)
    overall = flags.select(pl.lit(None, dtype=pl.Int64).alias("weather"), *aggregations)
    combined = pl.concat([per_weather, overall], how="vertical")

    return (
        combined.with_columns(
            (pl.col("tp") / (pl.col("tp") + pl.col("fp"))).round(4).alias("precision"),
            (pl.col("tp") / (pl.col("tp") + pl.col("fn"))).round(4).alias("recall"),
            (2 * pl.col("tp") / (2 * pl.col("tp") + pl.col("fp") + pl.col("fn")))
            .round(4)
            .alias("f1"),
            pl.lit(model).alias("model"),
        )
        .sort(["model", "weather"])
        .select(
            "model",
            "weather",
            "frames",
            "tp",
            "fp",
            "fn",
            "precision",
            "recall",
            "f1",
            "critical_failures",
            "poor_localizations",
        )
    )


def main() -> None:
    frames = []
    for profile in PROFILES:
        path = ensure_dataset(profile, n=5_000_000)
        print(f"⚖️  Ewaluacja profilu {profile} ({path.name})...")
        flags = compute_kpi_flags(load_detections(path))
        frames.append(summarize(flags, profile))

    comparison = pl.concat(frames)
    output_path = PROCESSED_DATA_DIR / "model_comparison.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    comparison.write_parquet(output_path)

    with pl.Config(tbl_rows=-1, tbl_width_chars=200):
        print(comparison)
    print(f"\n💾 Zapisano: {output_path}")

    overall = comparison.filter(pl.col("weather").is_null())
    v1, v2 = overall.filter(pl.col("model") == "v1"), overall.filter(pl.col("model") == "v2")
    recall_delta = (v2["recall"][0] - v1["recall"][0]) * 100
    critical_change = (1 - v2["critical_failures"][0] / v1["critical_failures"][0]) * 100
    print(
        f"📈 ALL: recall {v1['recall'][0]:.4f} → {v2['recall'][0]:.4f} "
        f"({recall_delta:+.1f} pp); critical failures {v1['critical_failures'][0]:,} → "
        f"{v2['critical_failures'][0]:,} (−{critical_change:.0f}%)"
    )


if __name__ == "__main__":
    main()
