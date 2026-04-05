import os

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from api.predictor import RISK_CONTEXT, calculate_live_risk
from api.schemas import PredictionResponse
from src.config import PROCESSED_DATA_PATH

APP_VERSION = "1.1.0"

app = FastAPI(
    title="Bengaluru Accident Risk API",
    version=APP_VERSION,
    description=(
        "Predicts location-level road accident risk in Bengaluru using a hybrid "
        "spatial + live context model."
    ),
)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

heatmap_data: list[list[float]] = []


@app.on_event("startup")
def load_heatmap_data() -> None:
    global heatmap_data

    print("Loading heatmap data...")
    heatmap_data = []

    if not os.path.exists(PROCESSED_DATA_PATH):
        print("Warning: processed training data not found. Heatmap will be empty.")
        return

    df = pd.read_csv(PROCESSED_DATA_PATH)

    required = {"lat", "lon", "dist_to_blackspot_km", "junction_complexity"}
    if not required.issubset(df.columns):
        print("Warning: required columns for heatmap surface are missing. Falling back to risk_label points.")
        fallback = df[df.get("risk_label", 0) == 1][["lat", "lon"]].values.tolist()
        heatmap_data = [[float(lat), float(lon), 0.8] for lat, lon in fallback]
        print(f"Loaded {len(heatmap_data)} fallback heatmap points")
        return

    heatmap_df = df.copy()
    heatmap_df["station_risk_score"] = heatmap_df.get("station_risk_score", 0.0)
    heatmap_df["station_trend_index"] = heatmap_df.get("station_trend_index", 1.0)

    # Continuous risk surface (not only label-based hotspots):
    # - spatial decay from known blackspots
    # - junction complexity
    # - multi-year station severity
    # - mild trend effect from station trend index
    dist_component = (1.0 / (1.0 + heatmap_df["dist_to_blackspot_km"])).clip(0.0, 1.0)
    junc_component = (heatmap_df["junction_complexity"] / 6.0).clip(0.0, 1.0)
    station_component = heatmap_df["station_risk_score"].clip(0.0, 1.0)
    trend_component = ((heatmap_df["station_trend_index"] - 1.0) * 0.5 + 0.5).clip(0.0, 1.0)

    heatmap_df["risk_surface"] = (
        (0.50 * dist_component)
        + (0.20 * junc_component)
        + (0.25 * station_component)
        + (0.05 * trend_component)
    ).clip(0.0, 1.0)

    # Build diverse bands instead of one hard threshold.
    p40 = float(heatmap_df["risk_surface"].quantile(0.40))
    p70 = float(heatmap_df["risk_surface"].quantile(0.70))
    p88 = float(heatmap_df["risk_surface"].quantile(0.88))

    low_band = heatmap_df[(heatmap_df["risk_surface"] >= p40) & (heatmap_df["risk_surface"] < p70)]
    mid_band = heatmap_df[(heatmap_df["risk_surface"] >= p70) & (heatmap_df["risk_surface"] < p88)]
    high_band = heatmap_df[heatmap_df["risk_surface"] >= p88]

    # Sample each band differently to preserve texture and avoid giant merged blobs.
    if len(low_band) > 4500:
        low_band = low_band.sample(4500, random_state=42)
    if len(mid_band) > 7000:
        mid_band = mid_band.sample(7000, random_state=42)
    if len(high_band) > 9000:
        high_band = high_band.sample(9000, random_state=42)

    filtered = pd.concat([low_band, mid_band, high_band], ignore_index=True)

    # Non-linear intensity scaling spreads values better across colors.
    filtered["intensity"] = (0.10 + (0.90 * (filtered["risk_surface"] ** 1.45))).clip(0.12, 1.0)

    # Tiny deterministic jitter to break visual plateaus when many points overlap.
    filtered["lat_jitter"] = (filtered["lat"] * 100000 % 7 - 3) * 0.000015
    filtered["lon_jitter"] = (filtered["lon"] * 100000 % 7 - 3) * 0.000015

    heatmap_data = [
        [
            float(row.lat + row.lat_jitter),
            float(row.lon + row.lon_jitter),
            float(row.intensity),
        ]
        for row in filtered.itertuples(index=False)
    ]

    print(
        f"Loaded {len(heatmap_data)} diverse heatmap points "
        f"(bands p40={p40:.3f}, p70={p70:.3f}, p88={p88:.3f})"
    )


@app.get("/")
def read_root() -> dict:
    return {
        "status": "online",
        "city": "Bengaluru",
        "api_version": APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "heatmap_points": len(heatmap_data)}


@app.get("/predict", response_model=PredictionResponse)
def get_prediction(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
) -> dict:
    return calculate_live_risk(lat, lon)


@app.get("/heatmap")
def get_heatmap() -> dict:
    return {"points": heatmap_data}


@app.get("/station-trends")
def get_station_trends(limit: int = Query(20, ge=5, le=100)) -> dict:
    rows = []
    for station_key, score in RISK_CONTEXT.station_scores.items():
        trend_index = float(RISK_CONTEXT.station_trend_indices.get(station_key, 1.0))
        name = RISK_CONTEXT.station_display_names.get(station_key, station_key)

        if score >= 0.75:
            tier = "Critical"
        elif score >= 0.5:
            tier = "High"
        elif score >= 0.3:
            tier = "Moderate"
        else:
            tier = "Watch"

        rows.append(
            {
                "station": name,
                "station_key": station_key,
                "risk_score": round(float(score), 3),
                "trend_index": round(trend_index, 3),
                "trend_direction": "Rising" if trend_index > 1.02 else ("Improving" if trend_index < 0.98 else "Stable"),
                "tier": tier,
                "history": RISK_CONTEXT.station_histories.get(station_key, []),
            }
        )

    by_risk = sorted(rows, key=lambda item: item["risk_score"], reverse=True)
    by_rising = sorted(rows, key=lambda item: item["trend_index"], reverse=True)
    by_improving = sorted(rows, key=lambda item: item["trend_index"])

    return {
        "city_trend_index": RISK_CONTEXT.city_trend_index,
        "total_stations": len(rows),
        "top_risk": by_risk[:limit],
        "top_rising": by_rising[: min(10, limit)],
        "top_improving": by_improving[: min(10, limit)],
    }
