# src/feature_engineering.py
import numpy as np
import pandas as pd
from src.config import REAL_BLACKSPOTS

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees).
    Result is in Kilometers.
    """
    # Convert decimal degrees to radians 
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a)) 
    r = 6371 # Radius of earth in kilometers
    return c * r

def get_nearest_blackspot(lat, lon):
    """
    Finds the distance to the nearest known blackspot.
    Returns: (min_distance_km, name_of_spot)
    """
    min_dist = float('inf')
    nearest_name = "None"
    
    for name, coords in REAL_BLACKSPOTS.items():
        b_lat, b_lon = coords
        dist = haversine_distance(lat, lon, b_lat, b_lon)
        if dist < min_dist:
            min_dist = dist
            nearest_name = name
            
    return min_dist, nearest_name

def label_data(row):
    """
    Creates the Target Variable (Y).
    Logic: High Risk (1) if within 500m of Blackspot OR Very Complex Junction.
    """
    if row['dist_to_blackspot_km'] <= 0.5:
        return 1
    elif row['junction_complexity'] >= 5: # 5-way intersection
        return 1
    else:
        return 0