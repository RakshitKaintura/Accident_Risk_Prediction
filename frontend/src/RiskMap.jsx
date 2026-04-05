import { useEffect, useMemo, useState } from "react";
import { Circle, MapContainer, Marker, Popup, TileLayer, useMap, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.heat";
import L from "leaflet";
import axios from "axios";

import RoutingControl from "./RoutingControl";

import icon from "leaflet/dist/images/marker-icon.png";
import iconShadow from "leaflet/dist/images/marker-shadow.png";
import "./RiskMap.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const CITY_CENTER = [12.9716, 77.5946];

const defaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});
L.Marker.prototype.options.icon = defaultIcon;

function HeatmapLayer({ apiBaseUrl, mode }) {
  const map = useMap();

  useEffect(() => {
    let layer;

    const loadHeatmap = async () => {
      try {
        const response = await axios.get(`${apiBaseUrl}/heatmap`);
        const rawPoints = response?.data?.points || [];
        const points =
          mode === "focused"
            ? rawPoints
                .filter((point) => point[2] >= 0.42)
                .map((point) => [point[0], point[1], Math.min(1, point[2] * 1.08)])
            : rawPoints.map((point) => [point[0], point[1], Math.max(0.08, point[2] * 0.88)]);
        if (points.length === 0) {
          return;
        }

        const settings =
          mode === "focused"
            ? {
                radius: 9,
                blur: 6,
                minOpacity: 0.22,
                maxZoom: 16,
                gradient: {
                  0.2: "#4a95f2",
                  0.45: "#f2d264",
                  0.68: "#ef9442",
                  0.88: "#df4f4f",
                  1.0: "#9f1748",
                },
              }
            : {
                radius: 16,
                blur: 13,
                minOpacity: 0.14,
                maxZoom: 14,
                gradient: {
                  0.1: "#2f6fd8",
                  0.28: "#4a95f2",
                  0.46: "#7bc4ff",
                  0.62: "#f2d264",
                  0.78: "#ef9442",
                  0.92: "#df4f4f",
                  1.0: "#b81f4d",
                },
              };

        layer = L.heatLayer(points, settings).addTo(map);
      } catch (error) {
        console.error("Heatmap load failed", error);
      }
    };

    loadHeatmap();

    return () => {
      if (layer) {
        map.removeLayer(layer);
      }
    };
  }, [apiBaseUrl, map, mode]);

  return null;
}

function ClickHandler({ onSelectPoint }) {
  useMapEvents({
    click(event) {
      onSelectPoint(event.latlng.lat, event.latlng.lng);
    },
  });
  return null;
}

function MapFlyTo({ coords }) {
  const map = useMap();

  useEffect(() => {
    if (coords) {
      map.flyTo(coords, 14, { duration: 0.7 });
    }
  }, [coords, map]);

  return null;
}

function riskColor(level) {
  if (level === "High") return "#d12c4a";
  if (level === "Medium") return "#e39a16";
  if (level === "Low") return "#2d8f47";
  return "#3e6a76";
}

function trafficTone(status) {
  if (status === "Congested") return "danger";
  if (status === "Moderate") return "warn";
  return "good";
}

function buildContributionRows(prediction) {
  const b = prediction?.data?.breakdown;
  if (!b) return [];

  const denom = Math.max(0.0001, b.pre_cap_score || prediction.data.risk_score || 0.0001);
  const rows = [
    { key: "Base (Model + Spatial)", value: b.base_probability_used },
    { key: "Traffic", value: b.traffic_modifier },
    { key: "Weather", value: b.weather_modifier },
    { key: "Station", value: b.station_modifier },
    { key: "City Trend", value: b.city_trend_modifier },
  ];

  return rows.map((row) => {
    const pct = (row.value / denom) * 100;
    return {
      ...row,
      pct: Number(pct.toFixed(1)),
      width: Math.min(100, Math.abs(pct)),
      isNegative: pct < 0,
    };
  });
}

function StationSparkline({ history }) {
  if (!history || history.length < 2) {
    return <div className="sparkline-empty">No trend</div>;
  }

  const values = history.map((item) => Number(item.total_cases || 0));
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = Math.max(1, maxVal - minVal);

  const width = 72;
  const height = 24;

  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * (width - 2) + 1;
      const y = height - 2 - ((value - minVal) / range) * (height - 4);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const rising = values[values.length - 1] >= values[0];

  return (
    <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Station trend sparkline">
      <polyline points={points} fill="none" stroke={rising ? "#d94f5f" : "#1f7a3a"} strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export default function RiskMap() {
  const [prediction, setPrediction] = useState(null);
  const [routePoints, setRoutePoints] = useState({ start: null, end: null });
  const [routeSummary, setRouteSummary] = useState(null);
  const [searchMode, setSearchMode] = useState("place");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [heatmapMode, setHeatmapMode] = useState("focused");
  const [stationTrends, setStationTrends] = useState(null);
  const [stationTrendLoading, setStationTrendLoading] = useState(true);

  const [placeQuery, setPlaceQuery] = useState("");
  const [startQuery, setStartQuery] = useState("");
  const [endQuery, setEndQuery] = useState("");

  const riskPercent = useMemo(() => {
    if (!prediction) return null;
    return (prediction.data.risk_score * 100).toFixed(1);
  }, [prediction]);
  const contributionRows = useMemo(() => buildContributionRows(prediction), [prediction]);

  useEffect(() => {
    const loadStationTrends = async () => {
      setStationTrendLoading(true);
      try {
        const response = await axios.get(`${API_BASE_URL}/station-trends?limit=8`);
        setStationTrends(response.data);
      } catch (fetchError) {
        console.error("Station trends load failed", fetchError);
        setStationTrends(null);
      } finally {
        setStationTrendLoading(false);
      }
    };

    loadStationTrends();
  }, []);

  const geocode = async (query) => {
    const text = query.trim();
    if (!text) {
      throw new Error("Please enter a location");
    }

    const response = await axios.get("https://nominatim.openstreetmap.org/search", {
      params: { format: "json", q: `${text}, Bengaluru` },
      timeout: 5000,
    });

    if (!response.data || response.data.length === 0) {
      throw new Error(`Location not found: ${text}`);
    }

    return [Number.parseFloat(response.data[0].lat), Number.parseFloat(response.data[0].lon)];
  };

  const runPrediction = async (lat, lon) => {
    setLoading(true);
    setError("");
    try {
      const response = await axios.get(`${API_BASE_URL}/predict`, {
        params: { lat, lon },
      });
      setPrediction({ lat, lng: lon, data: response.data });
      return response.data;
    } catch (err) {
      console.error("Prediction request failed", err);
      setError("Could not fetch risk prediction. Ensure backend is running on the configured API URL.");
      return null;
    } finally {
      setLoading(false);
    }
  };

  const handleMapSelect = async (lat, lon) => {
    setRoutePoints({ start: null, end: null });
    setRouteSummary(null);
    await runPrediction(lat, lon);
  };

  const handlePlaceSearch = async () => {
    setRoutePoints({ start: null, end: null });
    setRouteSummary(null);
    setError("");
    try {
      const [lat, lon] = await geocode(placeQuery);
      await runPrediction(lat, lon);
    } catch (err) {
      setError(err.message || "Unable to geocode this location.");
    }
  };

  const handleRouteSearch = async () => {
    setLoading(true);
    setError("");
    try {
      const startCoords = await geocode(startQuery);
      const endCoords = await geocode(endQuery);
      setPrediction(null);
      setRouteSummary(null);
      setRoutePoints({ start: startCoords, end: endCoords });
    } catch (err) {
      setError(err.message || "Unable to build route from provided locations.");
    } finally {
      setLoading(false);
    }
  };

  const onSearchSubmit = (event) => {
    event.preventDefault();
    if (searchMode === "place") {
      handlePlaceSearch();
      return;
    }
    handleRouteSearch();
  };

  return (
    <div className="layout-shell">
      <section className="map-panel">
        <MapContainer center={CITY_CENTER} zoom={12} className="leaflet-map" zoomControl>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <HeatmapLayer apiBaseUrl={API_BASE_URL} mode={heatmapMode} />
          <ClickHandler onSelectPoint={handleMapSelect} />

          {routePoints.start && routePoints.end && (
            <RoutingControl
              start={routePoints.start}
              end={routePoints.end}
              apiBaseUrl={API_BASE_URL}
              onRouteSummary={setRouteSummary}
            />
          )}

          {prediction && <MapFlyTo coords={[prediction.lat, prediction.lng]} />}

          {prediction && (
            <>
              <Marker position={[prediction.lat, prediction.lng]}>
                <Popup>Analyzed point</Popup>
              </Marker>
              <Circle
                center={[prediction.lat, prediction.lng]}
                radius={600}
                pathOptions={{
                  color: riskColor(prediction.data.risk_level),
                  fillColor: riskColor(prediction.data.risk_level),
                  fillOpacity: 0.35,
                }}
              />
            </>
          )}
        </MapContainer>
      </section>

      <aside className="control-panel">
        <header className="panel-header">
          <p className="eyebrow">Urban Road Safety Intelligence</p>
          <h1>SafeRoute Bengaluru</h1>
          <p className="subtext">
            AI-assisted risk scoring with live weather and traffic context for route and location safety checks.
          </p>
        </header>

        <div className="mode-switch" role="tablist" aria-label="Search mode switch">
          <button
            className={`mode-btn ${searchMode === "place" ? "active" : ""}`}
            onClick={() => setSearchMode("place")}
            type="button"
          >
            Place Analysis
          </button>
          <button
            className={`mode-btn ${searchMode === "route" ? "active" : ""}`}
            onClick={() => setSearchMode("route")}
            type="button"
          >
            Safe Route
          </button>
        </div>

        <div className="heatmap-switch" role="tablist" aria-label="Heatmap style switch">
          <button
            className={`mode-btn ${heatmapMode === "focused" ? "active" : ""}`}
            onClick={() => setHeatmapMode("focused")}
            type="button"
          >
            Focused Heatmap
          </button>
          <button
            className={`mode-btn ${heatmapMode === "diffuse" ? "active" : ""}`}
            onClick={() => setHeatmapMode("diffuse")}
            type="button"
          >
            Diffuse Heatmap
          </button>
        </div>

        <form className="search-card" onSubmit={onSearchSubmit}>
          {searchMode === "place" ? (
            <>
              <label htmlFor="place">Location in Bengaluru</label>
              <input
                id="place"
                type="text"
                placeholder="Ex: Indiranagar"
                value={placeQuery}
                onChange={(event) => setPlaceQuery(event.target.value)}
              />
              <button className="primary-btn" type="submit" disabled={loading}>
                {loading ? "Analyzing..." : "Analyze Risk"}
              </button>
            </>
          ) : (
            <>
              <label htmlFor="from">From</label>
              <input
                id="from"
                type="text"
                placeholder="Ex: Hebbal"
                value={startQuery}
                onChange={(event) => setStartQuery(event.target.value)}
              />
              <label htmlFor="to">To</label>
              <input
                id="to"
                type="text"
                placeholder="Ex: Silk Board"
                value={endQuery}
                onChange={(event) => setEndQuery(event.target.value)}
              />
              <button className="primary-btn route" type="submit" disabled={loading}>
                {loading ? "Computing..." : "Find Safer Route"}
              </button>
            </>
          )}
        </form>

        {error && <div className="error-banner">{error}</div>}

        <section className="result-card">
          {prediction ? (
            <>
              <p className="result-label">Risk Level</p>
              <h2 style={{ color: riskColor(prediction.data.risk_level) }}>{prediction.data.risk_level.toUpperCase()}</h2>
              <p className="probability">Probability: {riskPercent}%</p>

              <div className="context-grid">
                <div className="chip">
                  <span>Traffic</span>
                  <strong className={trafficTone(prediction.data.live_data.traffic)}>
                    {prediction.data.live_data.traffic}
                  </strong>
                </div>
                <div className="chip">
                  <span>Weather</span>
                  <strong>{prediction.data.live_data.weather}</strong>
                </div>
              </div>

              <ul className="fact-list">
                <li>Nearest blackspot: {prediction.data.live_data.nearest_blackspot}</li>
                <li>Distance: {prediction.data.live_data.distance_km} km</li>
              </ul>

              <ul className="factor-list">
                {prediction.data.factors.map((factor) => (
                  <li key={factor}>{factor}</li>
                ))}
              </ul>

              {contributionRows.length > 0 && (
                <div className="explain-box">
                  <p className="explain-title">Why This Risk</p>
                  {contributionRows.map((row) => (
                    <div className="explain-row" key={row.key}>
                      <div className="explain-label-line">
                        <span>{row.key}</span>
                        <strong className={row.isNegative ? "neg" : ""}>{row.pct}%</strong>
                      </div>
                      <div className="explain-track">
                        <div
                          className={`explain-fill ${row.isNegative ? "neg" : ""}`}
                          style={{ width: `${row.width}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : routePoints.start ? (
            routeSummary ? (
              <div className="route-scorecard">
                <p className="result-label">Route Risk Scorecard</p>
                <h3 className={`route-level ${routeSummary.routeRiskLevel.toLowerCase()}`}>
                  {routeSummary.routeRiskLevel} ({routeSummary.routeRiskScore})
                </h3>
                <ul className="fact-list">
                  <li>Distance: {routeSummary.totalDistanceKm} km</li>
                  <li>Estimated time: {routeSummary.totalTimeMin} min</li>
                  <li>Risk exposure: {routeSummary.riskExposurePct}%</li>
                  <li>High-risk segment share: {routeSummary.highRiskSharePct}%</li>
                  <li>Average intensity: {routeSummary.avgRiskIntensityPct}%</li>
                  <li>High-risk segments: {routeSummary.highRiskSegments}</li>
                </ul>
              </div>
            ) : (
              <div className="placeholder route-ready">Computing route scorecard...</div>
            )
          ) : (
            <div className="placeholder">
              Click on the map or search a place to inspect accident risk in real time.
            </div>
          )}
        </section>

        <section className="result-card">
          <p className="result-label">Station Trend Dashboard</p>
          {stationTrendLoading ? (
            <div className="placeholder">Loading station trend intelligence...</div>
          ) : stationTrends?.top_risk?.length ? (
            <div className="station-table">
              {stationTrends.top_risk.slice(0, 6).map((item) => (
                <div className="station-row" key={item.station_key}>
                  <div>
                    <strong>{item.station}</strong>
                    <p>{item.tier}</p>
                  </div>
                  <div className="station-metrics">
                    <StationSparkline history={item.history} />
                    <span>Risk {Math.round(item.risk_score * 100)}%</span>
                    <span className={item.trend_direction === "Rising" ? "danger" : item.trend_direction === "Improving" ? "good" : ""}>
                      Trend {item.trend_index}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="placeholder">Station trend data unavailable.</div>
          )}
        </section>
      </aside>
    </div>
  );
}
