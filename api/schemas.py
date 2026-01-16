# api/schemas.py
from pydantic import BaseModel

class PredictionRequest(BaseModel):
    lat: float
    lon: float

class PredictionResponse(BaseModel):
    risk_score: float      # 0.0 to 1.0
    risk_level: str        # "Low", "Medium", "High"
    factors: list[str]     # ["Near Blackspot", "Heavy Rain"]
    live_data: dict        # { "temp": 24, "traffic": "Congested" }