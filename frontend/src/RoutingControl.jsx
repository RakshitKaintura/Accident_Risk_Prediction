import { useEffect, useState, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet-routing-machine";
import "leaflet-routing-machine/dist/leaflet-routing-machine.css";
import axios from "axios";

export default function RoutingControl({ start, end }) {
  const map = useMap();
  const [riskZones, setRiskZones] = useState([]);
  const routingControlRef = useRef(null);

  // 1. FETCH RISK ZONES ON LOAD
  useEffect(() => {
    const fetchRiskZones = async () => {
      try {
        const response = await axios.get("http://127.0.0.1:8000/heatmap");
        const zones = response.data.points.map(p => ({ lat: p[0], lng: p[1] }));
        setRiskZones(zones);
      } catch (error) {
        console.error("❌ Failed to load risk data:", error);
      }
    };
    fetchRiskZones();
  }, []);

  // 2. CREATE & UPDATE ROUTE
  useEffect(() => {
    // Only run if we have a map, risk zones, AND valid start/end points
    if (!map || riskZones.length === 0 || !start || !end) return;

    // cleanup previous routing control
    if (routingControlRef.current) {
      try {
        map.removeControl(routingControlRef.current);
      } catch (e) { console.warn("Cleanup error", e); }
    }

    const routingControl = L.Routing.control({
      waypoints: [
        L.latLng(start[0], start[1]),
        L.latLng(end[0], end[1])
      ],
      routeWhileDragging: false,
      lineOptions: {
        styles: [{ color: "#3498db", opacity: 0.7, weight: 6 }]
      },
      show: false, // Keep UI clean
      addWaypoints: false,
      draggableWaypoints: false,
      fitSelectedRoutes: true,
      createMarker: function() { return null; } // Hide default pins (we can add custom ones if needed)
    }).addTo(map);

    routingControlRef.current = routingControl;

    // 3. AUDIT THE ROUTE
    routingControl.on("routesfound", function (e) {
      const routes = e.routes;
      const route = routes[0];
      const coordinates = route.coordinates;

      // Clean old red lines
      map.eachLayer((layer) => {
        if (layer.options && layer.options.color === "#e74c3c") {
          map.removeLayer(layer);
        }
      });

      let dangerSegments = [];
      let currentSegment = [];

      for (let i = 0; i < coordinates.length; i++) {
        const point = coordinates[i];
        let isRisky = false;

        // Proximity Check (~300m)
        for (let zone of riskZones) {
          const dist = Math.sqrt(Math.pow(point.lat - zone.lat, 2) + Math.pow(point.lng - zone.lng, 2));
          if (dist < 0.003) { 
            isRisky = true;
            break;
          }
        }

        if (isRisky) {
          currentSegment.push(point);
        } else {
          if (currentSegment.length > 0) {
            dangerSegments.push(currentSegment);
            currentSegment = [];
          }
        }
      }
      if (currentSegment.length > 0) dangerSegments.push(currentSegment);

      // Draw Danger Lines
      dangerSegments.forEach((segment) => {
        if (segment.length > 1) {
          L.polyline(segment, { color: "#e74c3c", weight: 10, opacity: 0.8 })
          .bindPopup("⚠️ <b>High Risk Segment</b>")
          .addTo(map);
        }
      });
    });

    return () => {
      if (routingControlRef.current) {
        try { map.removeControl(routingControlRef.current); } catch (e) {}
      }
    };
  }, [map, riskZones, start, end]); // Re-run when Start/End changes

  return null;
}