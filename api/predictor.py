# api/predictor.py
import xgboost as xgb
import pandas as pd
import numpy as np
import os
import random  # Added for simulation
from src.feature_engineering import get_nearest_blackspot
from src.config import REAL_BLACKSPOTS

# Load Model ONCE
MODEL_PATH = "data/models/blr_risk_xgboost.json"
model = xgb.XGBClassifier()

if os.path.exists(MODEL_PATH):
    model.load_model(MODEL_PATH)
    print("✅ Model loaded successfully!")
else:
    print("❌ CRITICAL: Model file not found.")

def calculate_live_risk(lat, lon):
    """
    Hybrid Logic:
    Final Risk = (Historical Model Probability) + (Live Traffic Penalty) + (Weather Penalty)
    """
    
    # --- STEP 1: SPATIAL MODEL (The Baseline) ---
    dist_km, spot_name = get_nearest_blackspot(lat, lon)
    
    # Prepare input for XGBoost
    input_data = pd.DataFrame([[dist_km, 3]], columns=['dist_to_blackspot_km', 'junction_complexity'])
    
    # Get the model's opinion (Is this a historically dangerous place?)
    base_probability = float(model.predict_proba(input_data)[0][1])
    
    # --- STEP 2: LIVE CONTEXT (The "Real-Time" Layer) ---
    # Since we might not have active API keys, we simulate traffic variability
    # In a real demo, you replace this with: traffic = call_tomtom_api(lat, lon)
    
    traffic_options = ["Free Flow", "Moderate", "Congested"]
    # 30% chance of hitting "Congested" traffic to show off the system features
    traffic_status = random.choices(traffic_options, weights=[40, 30, 30], k=1)[0]
    
    current_weather = "Clear"
    
    # --- STEP 3: APPLY PENALTIES ---
    live_modifier = 0.0
    factors = []

    # Factor A: Proximity (Historical)
    if base_probability > 0.4:
        factors.append(f"Proximity to {spot_name} ({dist_km:.2f}km)")

    # Factor B: Traffic (Live)
    if traffic_status == "Congested":
        live_modifier += 0.35  # Huge penalty for traffic jams
        factors.append("High Traffic Congestion")
    elif traffic_status == "Moderate":
        live_modifier += 0.10

    # Factor C: Weather (Live)
    if current_weather == "Rain":
        live_modifier += 0.20
        factors.append("Wet Road Surfaces")

    # --- STEP 4: CALCULATE FINAL SCORE ---
    # We combine the Model's "Knowledge" with the Live "Situation"
    final_score = base_probability + live_modifier
    
    # Cap it at 0.99 so we don't go over 100%
    final_score = min(final_score, 0.99)
    
    # Determine Label
    level = "Low"
    if final_score > 0.65: 
        level = "High"
    elif final_score > 0.30: 
        level = "Medium"

    # Explanation for Low Risk
    if level == "Low" and len(factors) == 0:
        factors.append("Safe Conditions")

    return {
        "risk_score": round(final_score, 2),
        "risk_level": level,
        "factors": factors,
        "live_data": {
            "weather": current_weather,
            "traffic": traffic_status,
            "nearest_blackspot": spot_name,
            "distance_km": round(dist_km, 2)
        }
    }