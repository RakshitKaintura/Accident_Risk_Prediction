from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    SAFE = "Safe"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class TrafficStatus(str, Enum):
    FREE_FLOW = "Free Flow"
    MODERATE = "Moderate"
    CONGESTED = "Congested"


class WeatherStatus(str, Enum):
    CLEAR = "Clear"
    CLOUDY = "Cloudy"
    RAIN = "Rain"


class LiveData(BaseModel):
    weather: WeatherStatus
    traffic: TrafficStatus
    traffic_speed_ratio: float = Field(ge=0.0)
    nearest_blackspot: str = Field(min_length=1)
    distance_km: float = Field(ge=0.0)
    station_name: Optional[str] = None
    station_risk_score: float = Field(ge=0.0, le=1.0)
    station_trend_index: float = Field(ge=0.0)
    city_trend_index: float = Field(ge=0.0)


class RiskBreakdown(BaseModel):
    ai_model_probability: float = Field(ge=0.0, le=1.0)
    math_spatial_risk: float = Field(ge=0.0, le=1.0)
    base_probability_used: float = Field(ge=0.0, le=1.0)
    traffic_modifier: float = Field(ge=-1.0, le=1.0)
    weather_modifier: float = Field(ge=-1.0, le=1.0)
    station_modifier: float = Field(ge=-1.0, le=1.0)
    city_trend_modifier: float = Field(ge=-1.0, le=1.0)
    total_modifier: float = Field(ge=-1.0, le=1.0)
    pre_cap_score: float = Field(ge=0.0)
    cap_applied: bool


class PredictionRequest(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)


class PredictionResponse(BaseModel):
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    factors: list[str]
    live_data: LiveData
    breakdown: RiskBreakdown
