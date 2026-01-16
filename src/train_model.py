# src/train_model.py
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import os
from src.config import PROCESSED_DATA_PATH

# Where to save the trained brain
MODEL_PATH = "data/models/blr_risk_xgboost.json"

def train():
    print("🧠 Starting Phase 2: Model Training...")
    
    # 1. Load Data
    if not os.path.exists(PROCESSED_DATA_PATH):
        print("❌ Error: Training data not found. Run Phase 1 first.")
        return

    df = pd.read_csv(PROCESSED_DATA_PATH)
    
    # 2. Prepare Features (X) and Target (y)
    # We drop names and coordinates for training, keeping only the mathematical features
    X = df[['dist_to_blackspot_km', 'junction_complexity']]
    y = df['risk_label']
    
    # 3. Split Data (80% Train, 20% Test)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 4. Calculate Imbalance Ratio
    # This is crucial! High risk zones are rare.
    # We tell the model: "Positive cases are worth X times more than negative cases"
    ratio = float(y_train.value_counts()[0]) / y_train.value_counts()[1]
    print(f"⚖️  Imbalance Ratio calculated: {ratio:.2f} (The model will weight accidents higher)")

    # 5. Initialize XGBoost
    model = xgb.XGBClassifier(
        objective='binary:logistic',
        scale_pos_weight=ratio,  # Fixes the imbalance
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        eval_metric='logloss'
    )
    
    # 6. Train
    print("💪 Training XGBoost Model...")
    model.fit(X_train, y_train)
    
    # 7. Evaluate
    print("\n📊 Model Evaluation (Test Set):")
    predictions = model.predict(X_test)
    print(classification_report(y_test, predictions))
    
    # 8. Save the Model
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    model.save_model(MODEL_PATH)
    print(f"✅ Model saved to: {MODEL_PATH}")
    print("   (The Backend will load this file to make predictions)")

if __name__ == "__main__":
    train()