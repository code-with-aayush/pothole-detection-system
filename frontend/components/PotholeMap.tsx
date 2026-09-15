"use client";

import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Pothole } from "@/types/pothole";

interface PotholeMapProps {
  potholes: Pothole[];
  selectedPotholeId?: string;
  onSelectPothole: (pothole: Pothole) => void;
}

// Map severity / resolved status to specified colors
function getMarkerColor(pothole: Pothole): string {
  if (pothole.status === "resolved") return "#10b981"; // green
  if (pothole.severity === "high") return "#ef4444"; // red
  if (pothole.severity === "medium") return "#f97316"; // orange
  return "#eab308"; // yellow for low
}

function createPotholeIcon(pothole: Pothole, isSelected: boolean) {
  const color = getMarkerColor(pothole);
  const size = isSelected ? 34 : 26;
  const stroke = isSelected ? "#ffffff" : "#0f172a";
  const strokeWidth = isSelected ? 3 : 2;

  const html = `
    <div style="
      display: flex;
      align-items: center;
      justify-content: center;
      width: ${size}px;
      height: ${size}px;
      border-radius: 50%;
      background-color: ${color};
      border: ${strokeWidth}px solid ${stroke};
      box-shadow: 0 4px 10px rgba(0,0,0,0.5);
      cursor: pointer;
      transition: transform 0.2s;
    ">
      <div style="width: 8px; height: 8px; border-radius: 50%; background: white;"></div>
    </div>
  `;

  return L.divIcon({
    html,
    className: "custom-pothole-pin",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  });
}

function MapUpdater({ selectedPothole }: { selectedPothole?: Pothole }) {
  const map = useMap();
  useEffect(() => {
    if (selectedPothole?.latitude && selectedPothole?.longitude) {
      map.panTo([selectedPothole.latitude, selectedPothole.longitude], { animate: true });
    }
  }, [selectedPothole, map]);
  return null;
}

export function PotholeMap({
  potholes,
  selectedPotholeId,
  onSelectPothole,
}: PotholeMapProps) {
  // Only plot potholes with valid numerical coordinates
  const validPotholes = useMemo(
    () =>
      potholes.filter(
        (p) =>
          typeof p.latitude === "number" &&
          typeof p.longitude === "number" &&
          !isNaN(p.latitude) &&
          !isNaN(p.longitude)
      ),
    [potholes]
  );

  const selectedPothole = useMemo(
    () => validPotholes.find((p) => p._id === selectedPotholeId),
    [validPotholes, selectedPotholeId]
  );

  const defaultCenter: [number, number] = [28.6139, 77.2090]; // Delhi NCR central

  return (
    <div className="relative w-full h-[350px] md:h-[520px] rounded-xl overflow-hidden border border-slate-800 bg-slate-950 z-10">
      <MapContainer
        center={defaultCenter}
        zoom={11}
        scrollWheelZoom={true}
        className="w-full h-full"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapUpdater selectedPothole={selectedPothole} />

        {validPotholes.map((pothole) => {
          const isSelected = pothole._id === selectedPotholeId;
          const icon = createPotholeIcon(pothole, isSelected);

          return (
            <Marker
              key={pothole._id}
              position={[pothole.latitude as number, pothole.longitude as number]}
              icon={icon}
              eventHandlers={{
                click: () => onSelectPothole(pothole),
              }}
            >
              <Popup className="pothole-map-popup">
                <div className="text-slate-900 p-1 min-w-[200px]">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span
                      className="px-1.5 py-0.5 text-[10px] font-bold rounded uppercase tracking-wider text-white"
                      style={{ backgroundColor: getMarkerColor(pothole) }}
                    >
                      {pothole.status === "resolved" ? "RESOLVED" : `${pothole.severity.toUpperCase()} SEVERITY`}
                    </span>
                    <span className="text-[11px] font-medium text-slate-500">
                      {pothole.authority?.shortName || "UNKNOWN"}
                    </span>
                  </div>

                  <p className="text-xs font-semibold text-slate-800 line-clamp-2 my-1">
                    {pothole.address || "Street location unavailable"}
                  </p>

                  <div className="text-[10px] text-slate-500 mb-2">
                    Detected: {new Date(pothole.detectedAt).toLocaleString()}
                  </div>

                  <button
                    type="button"
                    onClick={() => onSelectPothole(pothole)}
                    className="w-full py-1 text-center bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium rounded transition-colors"
                  >
                    View Details & Actions
                  </button>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>

      {/* Map Legend Overlay */}
      <div className="absolute bottom-3 left-3 z-[1000] bg-slate-950/90 border border-slate-800 p-2.5 rounded-lg text-xs backdrop-blur-sm shadow-xl pointer-events-auto">
        <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
          Map Legend
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
            <span className="text-[11px] text-slate-300">High Severity</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-orange-500" />
            <span className="text-[11px] text-slate-300">Medium Severity</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-yellow-500" />
            <span className="text-[11px] text-slate-300">Low Severity</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span className="text-[11px] text-slate-300">Resolved</span>
          </div>
        </div>
      </div>
    </div>
  );
}
