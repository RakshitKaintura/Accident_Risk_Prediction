from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.schemas import PredictionResponse
from api.predictor import calculate_live_risk
import pandas as pd
import os
from src.config import PROCESSED_DATA_PATH

app = FastAPI(title="Bengaluru Accident Risk API")

# Allow React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the High Risk Zones ONCE when server starts
# (This avoids reading the CSV 100 times a second)
print("⏳ Loading Heatmap Data...")
heatmap_data = []
if os.path.exists(PROCESSED_DATA_PATH):
    df = pd.read_csv(PROCESSED_DATA_PATH)
    # Filter only High Risk (Label 1) points
    high_risk_df = df[df['risk_label'] == 1]
    # Convert to list of [lat, lon, intensity]
    heatmap_data = high_risk_df[['lat', 'lon']].values.tolist()
    # Add intensity (1.0) to each point
    heatmap_data = [[lat, lon, 1.0] for lat, lon in heatmap_data]
    print(f"✅ Loaded {len(heatmap_data)} high-risk points for heatmap.")
else:
    print("⚠️ Warning: Training data not found. Heatmap will be empty.")

@app.get("/")
def read_root():
    return {"status": "System Online", "city": "Bengaluru"}

@app.get("/predict", response_model=PredictionResponse)
def get_prediction(lat: float, lon: float):
    return calculate_live_risk(lat, lon)

@app.get("/heatmap")
def get_heatmap():
    """Returns a list of high-risk coordinates: [[lat, lon, intensity], ...]"""
    return {"points": heatmap_data}