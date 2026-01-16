import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMapEvents, Circle, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.heat'; // Import the heatmap library
import L from 'leaflet';
import axios from 'axios';
import RoutingControl from './RoutingControl'; // <--- 1. NEW IMPORT

// --- LEAFLET ICON FIX ---
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

// --- HEATMAP COMPONENT ---
function HeatmapLayer() {
    const map = useMap();

    useEffect(() => {
        const fetchHeatmapData = async () => {
            try {
                const response = await axios.get("http://127.0.0.1:8000/heatmap");
                const points = response.data.points;

                if (points.length > 0) {
                    const heat = L.heatLayer(points, {
                        radius: 25,
                        blur: 15,
                        maxZoom: 15,
                        gradient: { 0.4: 'blue', 0.65: 'lime', 1: 'red' }
                    });
                    heat.addTo(map);
                    console.log(`🔥 Heatmap loaded with ${points.length} points.`);
                }
            } catch (error) {
                console.error("❌ Error loading heatmap:", error);
            }
        };

        fetchHeatmapData();
    }, [map]);

    return null;
}

// --- CLICK HANDLER ---
function ClickHandler({ setPrediction }) {
    useMapEvents({
        click: async (e) => {
            const { lat, lng } = e.latlng;
            console.log("📍 Clicked:", lat, lng);
            try {
                const response = await axios.get(`http://127.0.0.1:8000/predict?lat=${lat}&lon=${lng}`);
                setPrediction({ lat, lng, data: response.data });
            } catch (error) {
                console.error("API Error:", error);
            }
        },
    });
    return null;
}

// --- MAIN COMPONENT ---
export default function RiskMap() {
    const [prediction, setPrediction] = useState(null);
    const bengaluruCenter = [12.9716, 77.5946];

    const getRiskColor = (level) => {
        if (level === "High") return "#e74c3c";
        if (level === "Medium") return "#f39c12";
        return "#2ecc71";
    };

    return (
        <div style={{ display: "flex", height: "100vh", width: "100vw", fontFamily: "Arial, sans-serif" }}>
            
            {/* LEFT: MAP */}
            <div style={{ flex: 3, position: "relative" }}>
                <MapContainer center={bengaluruCenter} zoom={12} style={{ height: "100%", width: "100%" }}>
                    <TileLayer
                        attribution='&copy; OpenStreetMap'
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />
                    
                    {/* 🔥 2. ADDED ROUTING CONTROL HERE 🔥 */}
                    <RoutingControl />

                    <HeatmapLayer />

                    <ClickHandler setPrediction={setPrediction} />
                    
                    {/* Selected Point Marker */}
                    {prediction && (
                        <>
                            <Marker position={[prediction.lat, prediction.lng]}>
                                <Popup>Risk Analysis Point</Popup>
                            </Marker>
                            <Circle 
                                center={[prediction.lat, prediction.lng]}
                                pathOptions={{ 
                                    color: getRiskColor(prediction.data.risk_level),       
                                    fillColor: getRiskColor(prediction.data.risk_level),   
                                    fillOpacity: 0.4 
                                }}
                                radius={600} 
                            />
                        </>
                    )}
                </MapContainer>
            </div>

            {/* RIGHT: DASHBOARD */}
            <div style={{ flex: 1, padding: "20px", background: "#f4f4f9", borderLeft: "2px solid #ddd", overflowY: "auto" }}>
                <h2 style={{ borderBottom: "2px solid #333", paddingBottom: "10px" }}>🚦 SafeRoute AI</h2>
                <p style={{ color: "#666" }}>Click on the map for details.</p>

                {prediction ? (
                    <div style={{ marginTop: "20px", background: "white", padding: "20px", borderRadius: "10px", boxShadow: "0 4px 6px rgba(0,0,0,0.1)" }}>
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
                            <li style={{ padding: "8px 0" }}>🚗 <strong>Traffic:</strong> {prediction.data.live_data.traffic}</li>
                            <li style={{ padding: "8px 0" }}>🌦️ <strong>Weather:</strong> {prediction.data.live_data.weather}</li>
                        </ul>
                        <h4 style={{ borderBottom: "1px solid #eee", paddingBottom: "5px", marginTop: "20px" }}>⚠️ Risk Factors</h4>
                        {prediction.data.factors.length > 0 ? (
                            <ul style={{ paddingLeft: "20px", color: "#d35400" }}>
                                {prediction.data.factors.map((f, i) => <li key={i}>{f}</li>)}
                            </ul>
                        ) : (
                            <p style={{ color: "#27ae60" }}>✅ No immediate spatial hazards.</p>
                        )}
                    </div>
                ) : (
                    <div style={{ marginTop: "50px", textAlign: "center", color: "#aaa" }}>
                        <h3>Heatmap Loaded!</h3>
                        <p>Red zones indicate high historical accident density.</p>
                    </div>
                )}
            </div>
        </div>
    );
}