import os

import pandas as pd

from src.config import (
    CITY_YEARLY_ACCIDENTS_PATH,
    PROCESSED_DATA_PATH,
    RAW_DATA_PATH,
    STATION_WISE_2018_2020_PATH,
    STATION_WISE_2021_2022_PATH,
    STATION_WISE_2023_PATH,
    STATION_WISE_2024_PATH,
    STATION_WISE_ACCIDENTS_PATH,
)
from src.feature_engineering import get_nearest_blackspot, label_data
from src.risk_context import load_risk_context, station_profile_for_blackspot


REQUIRED_COLUMNS = {"lat", "lon", "junction_complexity"}


def main() -> None:
    print("Starting Phase 1: Data Pipeline...")

    if os.path.exists(RAW_DATA_PATH):
        print("Found existing raw data. Loading...")
        df = pd.read_csv(RAW_DATA_PATH)
    else:
        from src.data_loader import download_bengaluru_map

        df = download_bengaluru_map()

    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(f"Raw data is missing required columns: {sorted(missing_columns)}")

    print("Calculating distance to nearest blackspot...")

    proximity_results = df.apply(
        lambda row: get_nearest_blackspot(row["lat"], row["lon"]),
        axis=1,
        result_type="expand",
    )
    df[["dist_to_blackspot_km", "nearest_blackspot_name"]] = proximity_results

    print("Loading multi-year station profiles...")
    risk_context = load_risk_context(
        city_yearly_path=CITY_YEARLY_ACCIDENTS_PATH,
        station_wise_paths=[
            STATION_WISE_2018_2020_PATH,
            STATION_WISE_2021_2022_PATH,
            STATION_WISE_2023_PATH,
            STATION_WISE_2024_PATH,
            STATION_WISE_ACCIDENTS_PATH,
        ],
    )

    station_features = df["nearest_blackspot_name"].apply(
        lambda name: station_profile_for_blackspot(
            blackspot_name=name,
            station_scores=risk_context.station_scores,
            station_trends=risk_context.station_trend_indices,
        )
    )
    df[["station_name", "station_risk_score", "station_trend_index"]] = pd.DataFrame(
        station_features.tolist(), index=df.index
    )
    df["city_trend_index"] = risk_context.city_trend_index

    print("Generating risk labels...")
    df["risk_label"] = df.apply(label_data, axis=1)

    os.makedirs(os.path.dirname(PROCESSED_DATA_PATH), exist_ok=True)
    df.to_csv(PROCESSED_DATA_PATH, index=False)

    total_samples = len(df)
    high_risk = int(df["risk_label"].sum())
    share = (high_risk / total_samples) * 100 if total_samples else 0.0

    print("=" * 50)
    print("PHASE 1 COMPLETE")
    print(f"Training dataset: {PROCESSED_DATA_PATH}")
    print(f"Total samples: {total_samples}")
    print(f"High-risk samples: {high_risk} ({share:.2f}%)")
    print("=" * 50)


if __name__ == "__main__":
    main()
