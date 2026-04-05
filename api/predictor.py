from __future__ import annotations

import os
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import xgboost as xgb
from dotenv import load_dotenv

from src.config import CITY_YEARLY_ACCIDENTS_PATH, STATION_WISE_ACCIDENTS_PATH
from src.config import (
    STATION_WISE_2018_2020_PATH,
    STATION_WISE_2021_2022_PATH,
    STATION_WISE_2023_PATH,
    STATION_WISE_2024_PATH,
)
from src.feature_engineering import get_nearest_blackspot
from src.risk_context import load_risk_context, station_adjustment_for_blackspot

load_dotenv()

TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
MODEL_PATH = "data/models/blr_risk_xgboost.json"
REQUEST_TIMEOUT = 2
HTTP_SESSION = requests.Session()
HTTP_SESSION.trust_env = False

model = xgb.XGBClassifier()
MODEL_READY = False

if os.path.exists(MODEL_PATH):
    model.load_model(MODEL_PATH)
    MODEL_READY = True
    print("Model loaded successfully")
else:
    print("Warning: model file not found. Falling back to mathematical risk only.")

RISK_CONTEXT = load_risk_context(
    city_yearly_path=CITY_YEARLY_ACCIDENTS_PATH,
    station_wise_paths=[
        STATION_WISE_2018_2020_PATH,
        STATION_WISE_2021_2022_PATH,
        STATION_WISE_2023_PATH,
        STATION_WISE_2024_PATH,
        STATION_WISE_ACCIDENTS_PATH,
    ],
)
print(
    "Loaded external risk context: "
    f"city_trend_index={RISK_CONTEXT.city_trend_index}, "
    f"stations={len(RISK_CONTEXT.station_scores)}"
)


def get_real_weather(lat: float, lon: float) -> str:
    if not OPENWEATHER_API_KEY:
        return "Clear"

    try:
        response = HTTP_SESSION.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return "Clear"

    condition = data.get("weather", [{}])[0].get("main", "Clear")
    if condition in {"Rain", "Drizzle", "Thunderstorm"}:
        return "Rain"
    if condition in {"Clouds", "Mist", "Haze", "Fog"}:
        return "Cloudy"
    return "Clear"


def get_tomtom_traffic(lat: float, lon: float, dist_km: float | None = None) -> tuple[str, float]:
    if not TOMTOM_API_KEY:
        return get_fallback_traffic(dist_km)

    try:
        response = HTTP_SESSION.get(
            "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json",
            params={"key": TOMTOM_API_KEY, "point": f"{lat},{lon}"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return get_fallback_traffic(dist_km)

    flow = data.get("flowSegmentData", {})
    if not flow:
        return get_fallback_traffic(dist_km)

    current = flow.get("currentSpeed", 60)
    free_flow = flow.get("freeFlowSpeed", 60)
    if current is None or free_flow is None:
        return get_fallback_traffic(dist_km)

    ratio = current / free_flow if free_flow > 0 else 1.0

    if ratio < 0.5:
        return "Congested", float(ratio)
    if ratio < 0.8:
        return "Moderate", float(ratio)
    return "Free Flow", float(ratio)


def get_fallback_traffic(dist_km: float | None = None) -> tuple[str, float]:
    hour = datetime.now().hour
    # Distance-aware fallback: near known blackspots usually has at least moderate friction.
    if dist_km is not None:
        if dist_km < 0.7:
            return "Congested", 0.45
        if dist_km < 1.5:
            return "Moderate", 0.7

    if (8 <= hour <= 11) or (17 <= hour <= 21):
        return "Congested", 0.45
    if 12 <= hour <= 16:
        return "Moderate", 0.7
    return "Free Flow", 1.0


def get_continuous_traffic_modifier(speed_ratio: float, dist_km: float | None = None) -> float:
    ratio = max(0.2, min(1.0, float(speed_ratio)))
    congestion = 1.0 - ratio
    # Smooth curve:
    # - significant influence for vehicle-dense corridors
    # - steep rise as speed drops from free-flow
    modifier = 0.55 * (congestion ** 1.15)

    # Single-segment speed snapshots can report perfect free-flow even in urban friction zones.
    # Add a very small baseline only when ratio is near-perfect.
    if ratio >= 0.98:
        if dist_km is not None and dist_km < 1.0:
            modifier = max(modifier, 0.08)
        elif dist_km is not None and dist_km < 2.0:
            modifier = max(modifier, 0.05)
        else:
            modifier = max(modifier, 0.03)
    return float(round(modifier, 4))


def _predict_ai_probability(dist_km: float, station_risk_score: float, station_trend_index: float) -> float:
    if not MODEL_READY:
        return 0.0

    input_data = pd.DataFrame(
        [[min(dist_km, 5.0), 3, station_risk_score, station_trend_index]],
        columns=[
            "dist_to_blackspot_km",
            "junction_complexity",
            "station_risk_score",
            "station_trend_index",
        ],
    )

    try:
        feature_names = model.get_booster().feature_names
        if feature_names:
            input_data = input_data[feature_names]
    except Exception:
        pass

    try:
        return float(model.predict_proba(input_data)[0][1])
    except Exception:
        return 0.0


def calculate_live_risk(lat: float, lon: float) -> dict:
    dist_km, spot_name = get_nearest_blackspot(lat, lon)

    current_weather = get_real_weather(lat, lon)
    traffic_status, traffic_ratio = get_tomtom_traffic(lat, lon, dist_km)
    station_name, station_score, station_trend_index, station_modifier = station_adjustment_for_blackspot(
        blackspot_name=spot_name,
        station_scores=RISK_CONTEXT.station_scores,
        station_trends=RISK_CONTEXT.station_trend_indices,
        dist_km=dist_km,
    )

    ai_prob = _predict_ai_probability(dist_km, station_score, station_trend_index)
    # Keep spatial signal strong but avoid overwhelming all other dynamic factors.
    math_risk = float(0.80 * np.exp(-0.65 * dist_km))
    base_probability = float((0.75 * ai_prob) + (0.25 * math_risk))

    traffic_modifier = 0.0
    weather_modifier = 0.0
    city_trend_modifier = 0.0
    live_modifier = 0.0
    factors: list[str] = []

    if dist_km < 0.5:
        factors.append(f"High Risk Zone: {spot_name}")
    elif dist_km < 2.0:
        factors.append(f"Zone of Influence: {spot_name}")
    elif dist_km < 4.0:
        factors.append(f"Traffic corridor near {spot_name}")

    traffic_modifier = get_continuous_traffic_modifier(traffic_ratio, dist_km)
    live_modifier += traffic_modifier

    if traffic_status == "Congested":
        factors.append("Heavy traffic congestion")
    elif traffic_status == "Moderate":
        factors.append("Moderate traffic build-up")

    if current_weather == "Rain":
        weather_modifier = 0.20
        live_modifier += weather_modifier
        factors.append("Rainy conditions")
    elif current_weather == "Cloudy":
        weather_modifier = 0.04
        live_modifier += weather_modifier
        factors.append("Cloudy conditions (reduced visibility)")

    if station_modifier > 0:
        live_modifier += station_modifier
        factors.append(f"High-crash station context: {station_name}")

    if RISK_CONTEXT.city_trend_modifier != 0:
        city_trend_modifier = RISK_CONTEXT.city_trend_modifier
        live_modifier += city_trend_modifier
        if RISK_CONTEXT.city_trend_modifier > 0:
            factors.append("City-wide accident trend is elevated")
        else:
            factors.append("City-wide accident trend is improving")

    pre_cap_score = base_probability + live_modifier
    final_score = min(pre_cap_score, 0.98)
    cap_applied = pre_cap_score > 0.98

    if final_score > 0.70:
        level = "High"
    elif final_score > 0.35:
        level = "Medium"
    elif final_score > 0.15:
        level = "Low"
    else:
        level = "Safe"

    if level == "Safe":
        factors.append("No immediate hazards detected")

    return {
        "risk_score": round(final_score, 2),
        "risk_level": level,
        "factors": factors,
        "live_data": {
            "weather": current_weather,
            "traffic": traffic_status,
            "traffic_speed_ratio": float(round(traffic_ratio, 3)),
            "nearest_blackspot": spot_name,
            "distance_km": float(round(dist_km, 2)),
            "station_name": station_name,
            "station_risk_score": round(station_score, 3),
            "station_trend_index": round(station_trend_index, 3),
            "city_trend_index": RISK_CONTEXT.city_trend_index,
        },
        "breakdown": {
            "ai_model_probability": float(round(ai_prob, 4)),
            "math_spatial_risk": float(round(math_risk, 4)),
            "base_probability_used": float(round(base_probability, 4)),
            "traffic_modifier": float(round(traffic_modifier, 4)),
            "weather_modifier": float(round(weather_modifier, 4)),
            "station_modifier": float(round(station_modifier, 4)),
            "city_trend_modifier": float(round(city_trend_modifier, 4)),
            "total_modifier": float(round(live_modifier, 4)),
            "pre_cap_score": float(round(pre_cap_score, 4)),
            "cap_applied": bool(cap_applied),
        },
    }
