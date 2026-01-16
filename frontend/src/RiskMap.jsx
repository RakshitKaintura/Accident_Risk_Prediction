import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMapEvents, Circle, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.heat';
import L from 'leaflet';
import axios from 'axios';
import RoutingControl from './RoutingControl';

// --- ICONS ---
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';
let DefaultIcon = L.icon({
    iconUrl: icon, shadowUrl: iconShadow,
    iconSize: [25, 41], iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

// --- HEATMAP COMPONENT (RESTORED TO SOLID RED STYLE) ---
function HeatmapLayer() {
    const map = useMap();

    useEffect(() => {
        let heatLayer;

        axios.get("http://127.0.0.1:8000/heatmap").then(res => {
            const points = res.data.points;

            if (!points || points.length === 0) return;

            // Remove old heatmap safely
            map.eachLayer(layer => {
                if (layer._heat) map.removeLayer(layer);
            });

            heatLayer = L.heatLayer(points, {
                radius: 45,          // BIG radius for smooth regions
                blur: 35,            // High blur = no circles
                maxZoom: 13,
                minOpacity: 0.35,    // Transparent like IQAir
                max: 0.8,            // Prevent over-saturation
                gradient: {
                    0.0: '#2ecc71',  // green (safe)
                    0.4: '#f1c40f',  // yellow
                    0.6: '#e67e22',  // orange
                    0.8: '#e74c3c',  // red
                    1.0: '#8e44ad'   // dark purple (very high risk)
                }
            });

            heatLayer.addTo(map);
        });

        return () => {
            if (heatLayer) map.removeLayer(heatLayer);
        };
    }, [map]);

    return null;
}


// --- MAP CLICK HANDLER ---
function ClickHandler({ setPrediction }) {
    useMapEvents({
        click: async (e) => {
            const { lat, lng } = e.latlng;
            try {
                const response = await axios.get(`http://127.0.0.1:8000/predict?lat=${lat}&lon=${lng}`);
                setPrediction({ lat, lng, data: response.data });
            } catch (error) { console.error("API Error", error); }
        },
    });
    return null;
}

// --- MAIN COMPONENT ---
export default function RiskMap() {
    const [prediction, setPrediction] = useState(null);
    const [routePoints, setRoutePoints] = useState({ start: null, end: null });
    const [searchMode, setSearchMode] = useState("place"); 
    
    // Search Inputs
    const [placeQuery, setPlaceQuery] = useState("");
    const [startQuery, setStartQuery] = useState("");
    const [endQuery, setEndQuery] = useState("");

    // Helper: Geocode
    const geocode = async (query) => {
        try {
            const url = `https://nominatim.openstreetmap.org/search?format=json&q=${query}, Bengaluru`;
            const res = await axios.get(url);
            if (res.data && res.data.length > 0) {
                return [parseFloat(res.data[0].lat), parseFloat(res.data[0].lon)];
            }
            alert("Location not found: " + query);
            return null;
        } catch (e) { console.error("Geocoding error:", e); return null; }
    };

    const handlePlaceSearch = async () => {
        const coords = await geocode(placeQuery);
        if (coords) {
            setRoutePoints({ start: null, end: null });
            const response = await axios.get(`http://127.0.0.1:8000/predict?lat=${coords[0]}&lon=${coords[1]}`);
            setPrediction({ lat: coords[0], lng: coords[1], data: response.data });
        }
    };

    const handleRouteSearch = async () => {
        const startCoords = await geocode(startQuery);
        const endCoords = await geocode(endQuery);
        if (startCoords && endCoords) {
            setPrediction(null); 
            setRoutePoints({ start: startCoords, end: endCoords });
        }
    };

    const getRiskColor = (level) => {
        if (level === "High") return "#e74c3c";
        if (level === "Medium") return "#f39c12";
        return "#2ecc71";
    };

    function MapFlyTo({ coords }) {
        const map = useMap();
        useEffect(() => { if (coords) map.flyTo(coords, 14); }, [coords]);
        return null;
    }

    return (
        <div style={{ display: "flex", height: "100vh", width: "100vw", fontFamily: "Arial, sans-serif" }}>
            
            {/* LEFT: MAP */}
            <div style={{ flex: 3, position: "relative" }}>
                <MapContainer center={[12.9716, 77.5946]} zoom={12} style={{ height: "100%", width: "100%" }}>
                    <TileLayer attribution='&copy; OpenStreetMap' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                    <HeatmapLayer />
                    <ClickHandler setPrediction={setPrediction} />
                    
                    {routePoints.start && routePoints.end && (
                        <RoutingControl start={routePoints.start} end={routePoints.end} />
                    )}

                    {prediction && <MapFlyTo coords={[prediction.lat, prediction.lng]} />}
                    
                    {prediction && (
                        <>
                            <Marker position={[prediction.lat, prediction.lng]}>
                                <Popup>Selected Location</Popup>
                            </Marker>
                            <Circle center={[prediction.lat, prediction.lng]} radius={600} 
                                pathOptions={{ color: getRiskColor(prediction.data.risk_level), fillColor: getRiskColor(prediction.data.risk_level), fillOpacity: 0.4 }} />
                        </>
                    )}
                </MapContainer>
            </div>

            {/* RIGHT: DASHBOARD */}
            <div style={{ flex: 1, padding: "20px", background: "#f4f4f9", borderLeft: "2px solid #ddd", overflowY: "auto" }}>
                <h2 style={{ borderBottom: "2px solid #333", paddingBottom: "10px" }}>🚦 SafeRoute AI</h2>

                <div style={{ display: "flex", marginBottom: "15px", borderBottom: "1px solid #ccc" }}>
                    <button 
                        style={{ flex: 1, padding: "10px", border: "none", background: searchMode==="place" ? "#ddd" : "white", cursor: "pointer", fontWeight: "bold" }}
                        onClick={() => setSearchMode("place")}>
                        📍 Place Analysis
                    </button>
                    <button 
                        style={{ flex: 1, padding: "10px", border: "none", background: searchMode==="route" ? "#ddd" : "white", cursor: "pointer", fontWeight: "bold" }}
                        onClick={() => setSearchMode("route")}>
                        🚗 Safe Route
                    </button>
                </div>

                {/* --- INPUTS --- */}
                <div style={{ background: "white", padding: "15px", borderRadius: "8px", boxShadow: "0 2px 5px rgba(0,0,0,0.1)", marginBottom: "20px" }}>
                    {searchMode === "place" ? (
                        <>
                            <input 
                                type="text" placeholder="Enter location (e.g. Indiranagar)" 
                                value={placeQuery} onChange={e => setPlaceQuery(e.target.value)}
                                style={{ width: "93%", padding: "10px", marginBottom: "10px", borderRadius: "5px", border: "1px solid #ccc" }}
                            />
                            <button onClick={handlePlaceSearch} style={{ width: "100%", padding: "10px", background: "#3498db", color: "white", border: "none", borderRadius: "5px", cursor: "pointer" }}>
                                Analyze Risk
                            </button>
                        </>
                    ) : (
                        <>
                            <input 
                                type="text" placeholder="From (e.g. Hebbal)" 
                                value={startQuery} onChange={e => setStartQuery(e.target.value)}
                                style={{ width: "93%", padding: "10px", marginBottom: "10px", borderRadius: "5px", border: "1px solid #ccc" }}
                            />
                            <input 
                                type="text" placeholder="To (e.g. Silk Board)" 
                                value={endQuery} onChange={e => setEndQuery(e.target.value)}
                                style={{ width: "93%", padding: "10px", marginBottom: "10px", borderRadius: "5px", border: "1px solid #ccc" }}
                            />
                            <button onClick={handleRouteSearch} style={{ width: "100%", padding: "10px", background: "#2ecc71", color: "white", border: "none", borderRadius: "5px", cursor: "pointer" }}>
                                Find Safe Route
                            </button>
                        </>
                    )}
                </div>

                {/* --- RESULTS DASHBOARD --- */}
                {prediction ? (
                    <div style={{ background: "white", padding: "20px", borderRadius: "10px", boxShadow: "0 4px 6px rgba(0,0,0,0.1)" }}>
                        <div style={{ textAlign: "center", marginBottom: "20px" }}>
                            <h3 style={{ margin: 0, color: "#888" }}>RISK LEVEL</h3>
                            <h1 style={{ margin: "10px 0", fontSize: "3rem", color: getRiskColor(prediction.data.risk_level) }}>
                                {prediction.data.risk_level.toUpperCase()}
                            </h1>
                            <p>Probability: <strong>{(prediction.data.risk_score * 100).toFixed(1)}%</strong></p>
                        </div>
                        <h4 style={{ borderBottom: "1px solid #eee", paddingBottom: "5px" }}>📡 Live Context</h4>
                        <ul style={{ listStyle: "none", padding: 0 }}>
                            <li style={{ padding: "8px 0" }}>🛣️ <strong>Nearest Blackspot:</strong> <br/> {prediction.data.live_data.nearest_blackspot}</li>
                            <li style={{ padding: "8px 0" }}>📏 <strong>Distance:</strong> {prediction.data.live_data.distance_km} km</li>
                            <li style={{ padding: "8px 0" }}>🌦️ <strong>Weather:</strong> {prediction.data.live_data.weather}</li>
                            <li style={{ padding: "8px 0" }}>🚗 <strong>Traffic:</strong> {prediction.data.live_data.traffic}</li>
                        </ul>
                    </div>
                ) : (
                    <div style={{ textAlign: "center", color: "#666", marginTop: "30px" }}>
                        {routePoints.start ? (
                            <div style={{ color: "#2c3e50" }}>
                                <h3>🚗 Route Calculated</h3>
                                <p>Check the map for the blue path.</p>
                                <p style={{ color: "#e74c3c", fontWeight: "bold" }}>Red segments indicate high-risk zones.</p>
                            </div>
                        ) : (
                            <p>Use the search box above or click on the map.</p>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}