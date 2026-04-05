import os

import pandas as pd
import xgboost as xgb
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

from src.config import PROCESSED_DATA_PATH

MODEL_PATH = "data/models/blr_risk_xgboost.json"
FEATURE_COLUMNS = [
    "dist_to_blackspot_km",
    "junction_complexity",
    "station_risk_score",
    "station_trend_index",
]


def train() -> None:
    print("Starting Phase 2: Model Training...")

    if not os.path.exists(PROCESSED_DATA_PATH):
        print("Error: training data not found. Run Phase 1 first.")
        return

    df = pd.read_csv(PROCESSED_DATA_PATH)
    missing = [col for col in FEATURE_COLUMNS if col not in df.columns]
    if missing:
        print(f"Error: training data missing required columns: {missing}")
        print("Run Phase 1 dataset build again before training.")
        return

    X = df[FEATURE_COLUMNS]
    y = df["risk_label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    class_counts = y_train.value_counts()
    negative = int(class_counts.get(0, 0))
    positive = int(class_counts.get(1, 0))
    ratio = (negative / positive) if positive > 0 else 1.0

    print(f"Class balance (train): negatives={negative}, positives={positive}")
    print(f"Imbalance ratio used (scale_pos_weight): {ratio:.2f}")

    model = xgb.XGBClassifier(
        objective="binary:logistic",
        scale_pos_weight=ratio,
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        eval_metric="logloss",
    )

    print("Training XGBoost model...")
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    print("\nModel evaluation (test set):")
    print(classification_report(y_test, predictions, digits=4))
    print("Confusion matrix:")
    print(confusion_matrix(y_test, predictions))
    importances = model.feature_importances_
    ranked = sorted(zip(FEATURE_COLUMNS, importances), key=lambda x: x[1], reverse=True)
    print("Feature importances:")
    for name, score in ranked:
        print(f"  {name}: {score:.4f}")

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    model.save_model(MODEL_PATH)

    print(f"Model saved to: {MODEL_PATH}")


if __name__ == "__main__":
    train()
