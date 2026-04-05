# SafeRoute Bengaluru

SafeRoute Bengaluru is an AI-powered road safety intelligence platform that predicts accident risk by combining:
- Spatial risk near known blackspots
- A trained XGBoost model
- Live traffic and weather context

It provides an interactive map UI to analyze any location or compare route risk segments in Bengaluru.

## Why this project stands out

- Real-world framing: focuses on urban road safety, not toy prediction.
- Hybrid intelligence: combines model inference with interpretable mathematical risk decay.
- Full-stack implementation: data pipeline + ML model + FastAPI backend + React geospatial frontend.
- Practical UX: route-level risk highlighting and live contextual factors.

## Architecture

- `src/`: Data pipeline, feature engineering, and model training
- `api/`: FastAPI inference API and heatmap endpoints
- `frontend/`: React + Leaflet app for map visualization and risk analysis

Flow:
1. Build dataset from OSM intersections + Bengaluru blackspot proximity features.
2. Train XGBoost on engineered risk labels.
3. Serve predictions via FastAPI (`/predict`, `/heatmap`, `/health`).
4. Visualize risk zones and safer routes in the frontend.

## Key API Endpoints

- `GET /health`: Service health + heatmap point count
- `GET /predict?lat=<float>&lon=<float>`: Risk score, level, factors, live context
- `GET /heatmap`: High-risk map points

## Local setup

### 1) Backend

```bash
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn api.main:app --reload
```

### 2) Frontend

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Frontend runs on `http://localhost:5173` and calls backend via `VITE_API_BASE_URL`.

## Model pipeline commands

```bash
python -m src.build_dataset
python -m src.train_model
```

## Notes for reviewers

- Coordinates are validated at API boundaries.
- The system has fallback logic when live traffic/weather APIs are unavailable.
- Configuration is environment-driven for easier deployment.

## Future enhancements

- Add model performance dashboard (ROC, precision-recall, drift alerts)
- Introduce temporal traffic patterns by weekday/hour
- Add Docker + CI pipeline for one-command deploy
