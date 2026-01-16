# src/data_loader.py
import osmnx as ox
import pandas as pd
import os
from src.config import PLACE_NAME, RAW_DATA_PATH

def download_bengaluru_map():
    print(f"🛰️  Connecting to OpenStreetMap for: {PLACE_NAME}...")
    print("   (This helps us get real road coordinates. Please wait...)")
    
    # Download the road network (drive mode)
    # simplify=True removes small curves to make data cleaner
    graph = ox.graph_from_place(PLACE_NAME, network_type='drive', simplify=True)
    
    # Convert to standard Pandas DataFrames
    nodes, edges = ox.graph_to_gdfs(graph)
    
    print(f"✅  Download Complete! Found {len(nodes)} intersections.")
    
    # Extract only what we need
    # 'street_count' tells us if it's a T-junction (3) or a Crossroad (4)
    df = pd.DataFrame({
        'node_id': nodes.index,
        'lat': nodes.y,
        'lon': nodes.x,
        'junction_complexity': nodes.street_count
    })
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(RAW_DATA_PATH), exist_ok=True)
    
    # Save Raw Data
    df.to_csv(RAW_DATA_PATH, index=False)
    print(f"💾  Raw data saved to: {RAW_DATA_PATH}")
    return df