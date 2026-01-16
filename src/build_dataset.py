# src/build_dataset.py
import pandas as pd
import os
from src.data_loader import download_bengaluru_map
from src.feature_engineering import get_nearest_blackspot, label_data
from src.config import PROCESSED_DATA_PATH, RAW_DATA_PATH

def main():
    print("🚀 Starting Phase 1: Data Pipeline...")
    
    # 1. Check if raw data exists, else download it
    if os.path.exists(RAW_DATA_PATH):
        print("   Found existing raw data. Loading...")
        df = pd.read_csv(RAW_DATA_PATH)
    else:
        df = download_bengaluru_map()
        
    # 2. Apply Feature Engineering (The "Bengaluru Context")
    print("⚙️  Calculating Proximity to Blackspots (This creates spatial risk)...")
    
    # We apply the distance function to every row in the dataframe
    # This might take 10-20 seconds for the whole city
    proximity_results = df.apply(
        lambda row: get_nearest_blackspot(row['lat'], row['lon']), 
        axis=1, 
        result_type='expand'
    )
    
    df[['dist_to_blackspot_km', 'nearest_blackspot_name']] = proximity_results
    
    # 3. Create Labels (Target Variable)
    print("🏷️  Labeling data (0 = Low Risk, 1 = High Risk)...")
    df['risk_label'] = df.apply(label_data, axis=1)
    
    # 4. Save Final Training Set
    os.makedirs(os.path.dirname(PROCESSED_DATA_PATH), exist_ok=True)
    df.to_csv(PROCESSED_DATA_PATH, index=False)
    
    print("="*40)
    print(f"🎉 PHASE 1 COMPLETE!")
    print(f"   Training Data Saved: {PROCESSED_DATA_PATH}")
    print(f"   Total Samples: {len(df)}")
    print(f"   High Risk Zones Identified: {df['risk_label'].sum()}")
    print("="*40)

if __name__ == "__main__":
    main()