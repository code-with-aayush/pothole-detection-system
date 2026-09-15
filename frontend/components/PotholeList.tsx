"use client";

import { AlertCircle, Calendar, CheckCircle2, ChevronRight, Clock, MapPin, ShieldAlert, Wrench } from "lucide-react";
import { Pothole, Severity, Status } from "@/types/pothole";

interface PotholeListProps {
  potholes: Pothole[];
  selectedPotholeId?: string;
  onSelectPothole: (pothole: Pothole) => void;
  isLoading: boolean;
}

function getSeverityBadge(severity: Severity) {
  switch (severity) {
    case "high":
      return "bg-rose-500/10 text-rose-400 border-rose-500/30";
    case "medium":
      return "bg-orange-500/10 text-orange-400 border-orange-500/30";
    case "low":
      return "bg-yellow-500/10 text-yellow-400 border-yellow-500/30";
  }
}

function getStatusBadge(status: Status) {
  switch (status) {
    case "reported":
      return { bg: "bg-slate-800 text-slate-300 border-slate-700", icon: Clock, label: "Reported" };
    case "acknowledged":
      return { bg: "bg-sky-500/10 text-sky-400 border-sky-500/30", icon: AlertCircle, label: "Acknowledged" };
    case "in_progress":
      return { bg: "bg-amber-500/10 text-amber-400 border-amber-500/30", icon: Wrench, label: "In Progress" };
    case "resolved":
      return { bg: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30", icon: CheckCircle2, label: "Resolved" };
  }
}

export function PotholeList({
  potholes,
  selectedPotholeId,
  onSelectPothole,
  isLoading,
}: PotholeListProps) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4].map((n) => (
          <div
            key={n}
            className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl animate-pulse space-y-2.5"
          >
            <div className="flex justify-between items-center">
              <div className="h-4 w-24 bg-slate-800 rounded" />
              <div className="h-4 w-16 bg-slate-800 rounded" />
            </div>
            <div className="h-3.5 w-3/4 bg-slate-800 rounded" />
            <div className="h-3 w-1/2 bg-slate-800 rounded" />
          </div>
        ))}
      </div>
    );
  }

  if (potholes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 bg-slate-900/40 border border-dashed border-slate-800 rounded-xl text-center">
        <ShieldAlert className="w-10 h-10 text-slate-600 mb-2" />
        <h4 className="text-sm font-semibold text-slate-300">No live pothole reports yet.</h4>
        <p className="text-xs text-slate-500 mt-1 max-w-xs">
          Open Live Detect or upload a road frame to record verified pothole reports.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2.5 max-h-[580px] overflow-y-auto pr-1">
      {potholes.map((pothole) => {
        const isSelected = pothole._id === selectedPotholeId;
        const statusMeta = getStatusBadge(pothole.status);
        const StatusIcon = statusMeta.icon;
        const hasCoords = pothole.latitude !== null && pothole.longitude !== null;
        const sourceLabel =
          pothole.source === "mobile_camera"
            ? "Live Camera"
            : pothole.source === "live_upload"
            ? "Live Upload"
            : pothole.source === "upload"
            ? "Upload"
            : pothole.source || "Live";

        return (
          <button
            key={pothole._id}
            type="button"
            onClick={() => onSelectPothole(pothole)}
            className={`w-full text-left p-3.5 rounded-xl border transition-all cursor-pointer min-h-[44px] ${
              isSelected
                ? "bg-slate-800/90 border-amber-500 shadow-md ring-1 ring-amber-500/20"
                : "bg-slate-900/70 border-slate-800 hover:bg-slate-850 hover:border-slate-700"
            }`}
          >
            {/* Top row: Severity, Live Source Badge, Status, Authority */}
            <div className="flex items-center justify-between gap-2 mb-2">
              <div className="flex flex-wrap items-center gap-1.5">
                <span
                  className={`px-2 py-0.5 text-[10px] font-bold uppercase rounded border ${getSeverityBadge(
                    pothole.severity
                  )}`}
                >
                  {pothole.severity}
                </span>

                <span className="px-1.5 py-0.5 text-[9px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  {sourceLabel}
                </span>

                <span
                  className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded border ${statusMeta.bg}`}
                >
                  <StatusIcon className="w-2.5 h-2.5" />
                  <span>{statusMeta.label}</span>
                </span>

                {pothole.detectionCount && pothole.detectionCount > 1 && (
                  <span className="px-1.5 py-0.5 text-[9px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded font-mono">
                    {pothole.detectionCount}x Merged
                  </span>
                )}
              </div>

              <div className="text-right">
                <span className="text-[11px] font-semibold text-slate-300 block">
                  {pothole.authority?.shortName || "UNKNOWN"}
                </span>
              </div>
            </div>

            {/* Address */}
            <p className="text-xs font-semibold text-slate-200 line-clamp-1 mb-1.5">
              {pothole.address || "Street location unavailable"}
            </p>

            {/* Bottom row: Coordinates, Confidence, Report Status, Timestamp */}
            <div className="flex flex-wrap items-center justify-between text-[11px] text-slate-400 gap-y-1">
              <div className="flex items-center gap-1">
                <MapPin className={`w-3 h-3 ${hasCoords ? "text-slate-400" : "text-rose-400"}`} />
                <span>
                  {hasCoords
                    ? `${pothole.latitude?.toFixed(4)}, ${pothole.longitude?.toFixed(4)}`
                    : "Location unavailable"}
                </span>
                <span className="text-slate-600">•</span>
                <span className="text-amber-400 font-mono">
                  {(pothole.confidence * 100).toFixed(0)}% conf
                </span>
              </div>

              <div className="flex items-center gap-1.5">
                {pothole.reportStatus && (
                  <span
                    className={`text-[9px] px-1.5 py-0.2 rounded border font-mono uppercase ${
                      pothole.reportStatus === "sent"
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                        : pothole.reportStatus === "simulated"
                        ? "bg-blue-500/10 text-blue-400 border-blue-500/30"
                        : pothole.reportStatus === "failed"
                        ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                        : "bg-slate-800 text-slate-400 border-slate-700"
                    }`}
                  >
                    {pothole.reportStatus === "sent"
                      ? "Email Sent"
                      : pothole.reportStatus === "simulated"
                      ? "Demo Report"
                      : pothole.reportStatus === "dashboard_ticket_created"
                      ? "Ticket Created"
                      : pothole.reportStatus === "failed"
                      ? "Report Failed"
                      : pothole.reportStatus}
                  </span>
                )}
                <div className="flex items-center gap-1">
                  <Calendar className="w-3 h-3 text-slate-500" />
                  <span>
                    {new Date(pothole.detectedAt).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-500" />
                </div>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
