# src/config.py

# ==========================================
# 1. GEOSPATIAL SETTINGS
# ==========================================
PLACE_NAME = "Bengaluru, Karnataka, India"
CRS_PROJ = "EPSG:32643"  # Projected CRS for meters (UTM Zone 43N)

# ==========================================
# 2. BENGALURU BLACKSPOTS (GROUND TRUTH)
# ==========================================
# Coordinates derived from BTP 2024-25 High Risk Reports
# Format: "Name": (Latitude, Longitude)
REAL_BLACKSPOTS = {
    "Silk Board Junction": (12.9177, 77.6238),
    "Hebbal Flyover": (13.0359, 77.5970),
    "KR Puram Tin Factory": (13.0120, 77.6778),
    "Goraguntepalya": (13.0285, 77.5414),
    "Electronic City Toll": (12.8399, 77.6770),
    "Ibbalur Junction (ORR)": (12.9207, 77.6626),
    "Marathahalli Bridge": (12.9569, 77.7011),
    "Dairy Circle": (12.9363, 77.6058),
    "Banashankari Signal": (12.9259, 77.5702),
    "Summanahalli Junction": (13.0016, 77.5190),
    "Koramangala Sony Signal": (12.9367, 77.6259),
    "Nayandahalli Junction": (12.9409, 77.5265)
}

# ==========================================
# 3. DATA PATHS
# ==========================================
RAW_DATA_PATH = "data/raw/bengaluru_nodes.csv"
PROCESSED_DATA_PATH = "data/processed/training_data.csv"
CITY_YEARLY_ACCIDENTS_PATH = "data/NEW DATA/a583a07c-731b-4e8d-b0cb-d06e76ccc00c.csv"
STATION_WISE_ACCIDENTS_PATH = "data/NEW DATA/btp_2025_station_wise.csv"
STATION_WISE_2018_2020_PATH = "data/NEW DATA/aef42379-f1f7-4a3b-94f5-5f344e7120f2.csv"
STATION_WISE_2021_2022_PATH = "data/NEW DATA/492d3dc6-ffc3-4b0e-b7d9-176d0ef7f1ec.csv"
STATION_WISE_2023_PATH = "data/NEW DATA/abc5af52-08a7-4435-8ba1-12b99f62ee28.csv"
STATION_WISE_2024_PATH = "data/NEW DATA/74e645e3-85d2-4d81-a133-4f346f87fdd6.csv"
