from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import requests
from datetime import datetime
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
# Load environment variables from the .env file at the root
load_dotenv()

# Get the key safely. If not found, it defaults to None (triggering simulation mode)
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")

app = FastAPI()
# ... (rest of your code remains the same)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. LIVE WEATHER API (Open-Meteo - Free, No Key) ---
def get_live_weather(lat, lon):
    try:
        # Open-Meteo is amazing: Free, No Key, Accurate
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        response = requests.get(url, timeout=2)
        data = response.json()
        
        # Parse WMO Codes (World Meteorological Organization standard)
        wmo_code = data['current_weather']['weathercode']
        is_day = data['current_weather']['is_day']
        temp = data['current_weather']['temperature']
        
        if wmo_code in [0, 1]: 
            condition = "Clear ☀️" if is_day else "Clear 🌙"
        elif wmo_code in [2, 3]: 
            condition = "Cloudy ☁️"
        elif wmo_code in [51, 53, 55, 61, 63, 65, 80, 81, 82]: 
            condition = "Rainy 🌧️"
        elif wmo_code >= 95: 
            condition = "Stormy ⛈️"
        else: 
            condition = "Moderate 🌤️"
            
        return condition, wmo_code, temp
    except:
        return "Unknown 🌤️", 0, 25.0

# --- 2. TRAFFIC API (Hybrid: TomTom + Simulation) ---
def get_traffic_data(lat, lon):
    # OPTION A: Use Real TomTom API (If key exists)
    if TOMTOM_API_KEY:
        try:
            url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?key={TOMTOM_API_KEY}&point={lat},{lon}"
            response = requests.get(url, timeout=2)
            data = response.json()
            
            flow = data['flowSegmentData']
            current_speed = flow['currentSpeed']
            free_flow_speed = flow['freeFlowSpeed']
            confidence = flow['confidence'] # 0 to 1
            
            # Calculate Congestion Level
            congestion_ratio = current_speed / free_flow_speed
            
            if congestion_ratio < 0.5:
                return f"Heavy Congestion ({current_speed} km/h) 🟥", 1.5
            elif congestion_ratio < 0.8:
                return f"Moderate Flow ({current_speed} km/h) 🟨", 1.2
            else:
                return f"Free Flow ({current_speed} km/h) 🟩", 1.0
        except:
            print("⚠️ TomTom API Error. Falling back to simulation.")
            pass # Fallback to simulation if API fails

    # OPTION B: Smart Simulation (Time-Based Fallback)
    current_hour = datetime.now().hour
    # Bengaluru Peak Hours: 8-11 AM and 5-9 PM
    if (8 <= current_hour <= 11) or (17 <= current_hour <= 21):
        return "High (Peak Hour) 🚗🟥", 1.4
    elif (12 <= current_hour <= 16):
        return "Moderate 🚗🟨", 1.2
    else:
        return "Low (Free Flow) 🚗🟩", 1.0

# --- API ENDPOINTS ---

@app.get("/")
def home():
    return {"message": "SafeRoute AI Risk Engine Active"}

@app.get("/heatmap")
def get_heatmap():
    # Simulate hotspots (Lat, Lon, Intensity)
    # In a real app, this comes from your database
    points = [
        [12.9716, 77.5946, 1.0], [12.9352, 77.6245, 0.9], 
        [12.9141, 77.6109, 0.8], [12.9915, 77.5703, 0.7], 
        [13.0358, 77.5970, 0.9], [12.9081, 77.6476, 0.6], 
        [12.9698, 77.7500, 0.8], [12.9250, 77.5890, 0.75]
    ]
    # Add noise for realism
    for _ in range(30):
        lat = 12.9 + np.random.uniform(-0.05, 0.1)
        lon = 77.6 + np.random.uniform(-0.05, 0.1)
        points.append([lat, lon, np.random.uniform(0.4, 0.7)])
    return {"points": points}

@app.get("/predict")
def predict_risk(lat: float, lon: float):
    # 1. Base Model Logic (Simulated XGBoost)
    np.random.seed(int(lat * 1000 + lon * 1000))
    base_risk = np.random.uniform(0.3, 0.7)
    
    # 2. Get LIVE Context
    weather_cond, weather_code, temp = get_live_weather(lat, lon)
    traffic_cond, traffic_mult = get_traffic_data(lat, lon)
    
    # 3. Apply Multipliers
    # Rain increases risk by 25%
    weather_mult = 1.25 if "Rain" in weather_cond or "Storm" in weather_cond else 1.0
    
    final_score = base_risk * traffic_mult * weather_mult
    final_score = min(final_score, 0.98) # Cap at 98%
    
    # 4. Determine Output
    if final_score > 0.75:
        level = "High"
        factors = ["Accident Prone Zone", traffic_cond]
    elif final_score > 0.5:
        level = "Medium"
        factors = [traffic_cond]
    else:
        level = "Low"
        factors = ["Safe Conditions"]

    if weather_mult > 1.0:
        factors.append(f"Weather: {weather_cond}")

    return {
        "risk_level": level,
        "risk_score": final_score,
        "live_data": {
            "weather": f"{weather_cond} ({temp}°C)",
            "traffic": traffic_cond,
            "nearest_blackspot": "Silk Board Junction",
            "distance_km": round(np.random.uniform(0.2, 4.0), 1)
        },
        "factors": factors
    }