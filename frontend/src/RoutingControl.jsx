import { useEffect, useRef, useState } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet-routing-machine";
import "leaflet-routing-machine/dist/leaflet-routing-machine.css";
import axios from "axios";

export default function RoutingControl({ start, end, apiBaseUrl, onRouteSummary }) {
  const map = useMap();
  const [riskZones, setRiskZones] = useState([]);
  const routingControlRef = useRef(null);
  const dangerLayersRef = useRef([]);

  useEffect(() => {
    const fetchRiskZones = async () => {
      try {
        const response = await axios.get(`${apiBaseUrl}/heatmap`);
        const zones = response.data.points.map((point) => ({ lat: point[0], lng: point[1], intensity: point[2] || 0.4 }));
        setRiskZones(zones);
      } catch (error) {
        console.error("Failed to load risk data", error);
      }
    };

    fetchRiskZones();
  }, [apiBaseUrl]);

  useEffect(() => {
    if (!map || riskZones.length === 0 || !start || !end) {
      return undefined;
    }

    if (routingControlRef.current) {
      try {
        map.removeControl(routingControlRef.current);
      } catch {
        // no-op cleanup
      }
    }

    dangerLayersRef.current.forEach((layer) => map.removeLayer(layer));
    dangerLayersRef.current = [];

    const routingControl = L.Routing.control({
      waypoints: [L.latLng(start[0], start[1]), L.latLng(end[0], end[1])],
      routeWhileDragging: false,
      lineOptions: {
        styles: [{ color: "#1f6feb", opacity: 0.75, weight: 6 }],
      },
      show: false,
      addWaypoints: false,
      draggableWaypoints: false,
      fitSelectedRoutes: true,
      createMarker() {
        return null;
      },
    }).addTo(map);

    routingControlRef.current = routingControl;

    routingControl.on("routesfound", (event) => {
      dangerLayersRef.current.forEach((layer) => map.removeLayer(layer));
      dangerLayersRef.current = [];

      const route = event.routes[0];
      const coordinates = route?.coordinates ?? [];
      const summary = route?.summary ?? {};
      const dangerSegments = [];
      let currentSegment = [];
      let riskyPoints = 0;
      let weightedIntensitySum = 0;
      let highIntensityPoints = 0;

      coordinates.forEach((point) => {
        const nearbyIntensities = [];

        riskZones.forEach((zone) => {
          const latDiff = point.lat - zone.lat;
          const lngDiff = point.lng - zone.lng;
          const euclidean = Math.sqrt(latDiff * latDiff + lngDiff * lngDiff);
          if (euclidean < 0.003) {
            nearbyIntensities.push(zone.intensity);
          }
        });

        const isRisky = nearbyIntensities.length > 0;
        const localIntensity = isRisky ? Math.max(...nearbyIntensities) : 0;

        if (isRisky) {
          riskyPoints += 1;
          weightedIntensitySum += localIntensity;
          if (localIntensity >= 0.65) {
            highIntensityPoints += 1;
          }
          currentSegment.push(point);
          return;
        }

        if (currentSegment.length > 0) {
          dangerSegments.push(currentSegment);
          currentSegment = [];
        }
      });

      if (currentSegment.length > 0) {
        dangerSegments.push(currentSegment);
      }

      const totalPoints = Math.max(1, coordinates.length);
      const riskExposureRatio = riskyPoints / totalPoints;
      const avgRiskIntensity = riskyPoints > 0 ? weightedIntensitySum / riskyPoints : 0;
      const highRiskShare = riskyPoints > 0 ? highIntensityPoints / riskyPoints : 0;
      const routeRiskScore = Math.min(
        100,
        Math.round((riskExposureRatio * 70 + avgRiskIntensity * 20 + highRiskShare * 10) * 100) / 100,
      );

      let routeRiskLevel = "Low";
      if (routeRiskScore >= 75) {
        routeRiskLevel = "High";
      } else if (routeRiskScore >= 45) {
        routeRiskLevel = "Medium";
      }

      if (onRouteSummary) {
        onRouteSummary({
          totalDistanceKm: Number(((summary.totalDistance || 0) / 1000).toFixed(2)),
          totalTimeMin: Number(((summary.totalTime || 0) / 60).toFixed(1)),
          riskExposurePct: Number((riskExposureRatio * 100).toFixed(1)),
          highRiskSharePct: Number((highRiskShare * 100).toFixed(1)),
          avgRiskIntensityPct: Number((avgRiskIntensity * 100).toFixed(1)),
          routeRiskScore,
          routeRiskLevel,
          highRiskSegments: dangerSegments.length,
        });
      }

      dangerSegments.forEach((segment) => {
        if (segment.length < 2) {
          return;
        }

        const layer = L.polyline(segment, {
          color: "#d12c4a",
          weight: 9,
          opacity: 0.85,
        })
          .bindPopup("High-risk segment")
          .addTo(map);

        dangerLayersRef.current.push(layer);
      });
    });

    return () => {
      if (routingControlRef.current) {
        try {
          map.removeControl(routingControlRef.current);
        } catch {
          // no-op cleanup
        }
      }
      dangerLayersRef.current.forEach((layer) => map.removeLayer(layer));
      dangerLayersRef.current = [];
    };
  }, [map, riskZones, start, end, onRouteSummary]);

  return null;
}
