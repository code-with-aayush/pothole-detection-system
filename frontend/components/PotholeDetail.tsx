"use client";

import { useState } from "react";
import Image from "next/image";
import {
  Building2,
  History,
  ImageOff,
  MapPin,
  Send,
  X,
} from "lucide-react";
import { Pothole, Status } from "@/types/pothole";
import { getFullImageUrl, updatePotholeStatus, generatePotholeReport } from "@/lib/api";

interface PotholeDetailProps {
  pothole: Pothole | null;
  onClose: () => void;
  onUpdatePothole: (updated: Pothole) => void;
}

export function PotholeDetail({
  pothole,
  onClose,
  onUpdatePothole,
}: PotholeDetailProps) {
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const [imageFailed, setImageFailed] = useState(false);

  if (!pothole) return null;

  const handleStatusChange = async (targetStatus: Status) => {
    try {
      setIsUpdatingStatus(true);
      setActionFeedback(null);
      const updated = await updatePotholeStatus(
        pothole._id,
        targetStatus,
        `Status changed to ${targetStatus} via dashboard`
      );
      onUpdatePothole(updated);
      setActionFeedback({
        type: "success",
        message: `Status successfully updated to ${targetStatus.replace("_", " ")}`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update status";
      setActionFeedback({ type: "error", message: msg });
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  const handleGenerateReport = async () => {
    try {
      setIsGeneratingReport(true);
      setActionFeedback(null);
      const res = await generatePotholeReport(pothole._id);
      if (res.pothole) {
        onUpdatePothole(res.pothole);
      }
      setActionFeedback({
        type: "success",
        message: res.message || "Report processed successfully",
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to generate report";
      setActionFeedback({ type: "error", message: msg });
    } finally {
      setIsGeneratingReport(false);
    }
  };

  const imageUrl = getFullImageUrl(pothole.imageUrl);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 sm:p-5 flex flex-col gap-4 text-slate-200">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-slate-800 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-white">Incident Details</h3>
            <span className="text-xs font-mono text-slate-400">#{pothole._id.slice(-8)}</span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Detected on {new Date(pothole.detectedAt).toLocaleString()}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          title="Close detail panel"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Action feedback toast */}
      {actionFeedback && (
        <div
          className={`p-2.5 rounded-lg text-xs border ${
            actionFeedback.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
              : "bg-rose-500/10 border-rose-500/30 text-rose-300"
          }`}
        >
          {actionFeedback.message}
        </div>
      )}

      {/* Evidence Image */}
      <div className="relative w-full h-48 sm:h-56 bg-slate-950 rounded-lg overflow-hidden border border-slate-800 flex items-center justify-center">
        {imageUrl && !imageFailed ? (
          <Image
            src={imageUrl}
            alt="Pothole evidence"
            fill
            unoptimized
            priority
            className="object-contain"
            onError={() => setImageFailed(true)}
          />

        ) : (
          <div className="flex flex-col items-center gap-2 text-slate-600">
            <ImageOff className="w-8 h-8" />
            <span className="text-xs">No evidence image available</span>
          </div>
        )}
      </div>

      {/* Primary Key-Value Grid */}
      <div className="grid grid-cols-2 gap-2.5 text-xs">
        <div className="p-2.5 bg-slate-950/60 border border-slate-800 rounded-lg">
          <span className="text-slate-400 block text-[10px] uppercase font-semibold">Severity</span>
          <span
            className={`font-bold capitalize ${
              pothole.severity === "high"
                ? "text-rose-400"
                : pothole.severity === "medium"
                ? "text-orange-400"
                : "text-yellow-400"
            }`}
          >
            {pothole.severity} ({(pothole.confidence * 100).toFixed(1)}% conf)
          </span>
        </div>

        <div className="p-2.5 bg-slate-950/60 border border-slate-800 rounded-lg">
          <span className="text-slate-400 block text-[10px] uppercase font-semibold">Report Status</span>
          <span
            className={`font-bold ${
              pothole.reportStatus === "sent"
                ? "text-emerald-400"
                : pothole.reportStatus === "simulated"
                ? "text-blue-400"
                : pothole.reportStatus === "failed"
                ? "text-rose-400"
                : "text-amber-400"
            }`}
          >
            {pothole.reportStatus === "sent"
              ? "Email sent successfully"
              : pothole.reportStatus === "simulated"
              ? "Demo report generated"
              : pothole.reportStatus === "dashboard_ticket_created"
              ? "Dashboard ticket created"
              : pothole.reportStatus === "failed"
              ? "Report failed"
              : pothole.reportStatus || "Ticket Created"}
          </span>
        </div>

        <div className="p-2.5 bg-slate-950/60 border border-slate-800 rounded-lg">
          <span className="text-slate-400 block text-[10px] uppercase font-semibold">Report Channel</span>
          <span className="font-semibold text-slate-200">
            {pothole.reportChannel === "dashboard_ticket"
              ? "Dashboard Ticket"
              : pothole.reportChannel || "Dashboard Ticket"}
          </span>
        </div>

        <div className="p-2.5 bg-slate-950/60 border border-slate-800 rounded-lg">
          <span className="text-slate-400 block text-[10px] uppercase font-semibold">Detections</span>
          <span className="font-semibold text-white">
            {pothole.detectionCount && pothole.detectionCount > 1
              ? `${pothole.detectionCount} (Merged)`
              : "1 (Initial)"}
          </span>
        </div>

        <div className="p-2.5 bg-slate-950/60 border border-slate-800 rounded-lg col-span-2">
          <span className="text-slate-400 block text-[10px] uppercase font-semibold">Last Detected</span>
          <span className="text-slate-300 font-mono text-[11px]">
            {new Date(pothole.lastDetectedAt || pothole.detectedAt).toLocaleString()}
          </span>
        </div>

        <div className="p-2.5 bg-slate-950/60 border border-slate-800 rounded-lg col-span-2">
          <span className="text-slate-400 block text-[10px] uppercase font-semibold flex items-center gap-1 mb-0.5">
            <Building2 className="w-3 h-3 text-slate-400" />
            Responsible Authority
          </span>
          <div className="font-semibold text-white">
            {pothole.authority?.name || "Unassigned Road Authority"}
          </div>
          <div className="text-[11px] text-slate-400">
            {pothole.authority?.email || "No contact email"}
          </div>
        </div>

        <div className="p-2.5 bg-slate-950/60 border border-slate-800 rounded-lg col-span-2">
          <span className="text-slate-400 block text-[10px] uppercase font-semibold flex items-center gap-1 mb-0.5">
            <MapPin className="w-3 h-3 text-slate-400" />
            Location & Coordinates
          </span>
          <div className="font-medium text-slate-200">
            {pothole.address || "Street location unavailable"}
          </div>
          <div className="text-[11px] text-slate-400 font-mono mt-0.5">
            {pothole.latitude !== null && pothole.longitude !== null
              ? `Lat: ${pothole.latitude.toFixed(6)}, Lng: ${pothole.longitude.toFixed(6)}`
              : "No GPS coordinates logged"}
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="border-t border-slate-800 pt-3 space-y-2">
        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
          Operational Actions
        </span>

        <div className="grid grid-cols-3 gap-2">
          <button
            type="button"
            disabled={isUpdatingStatus || pothole.status === "acknowledged"}
            onClick={() => handleStatusChange("acknowledged")}
            className="px-2.5 py-2 text-xs font-medium bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed text-slate-200 border border-slate-700 rounded-lg transition-colors min-h-[44px]"
          >
            Acknowledge
          </button>

          <button
            type="button"
            disabled={isUpdatingStatus || pothole.status === "in_progress"}
            onClick={() => handleStatusChange("in_progress")}
            className="px-2.5 py-2 text-xs font-medium bg-amber-500/10 hover:bg-amber-500/20 disabled:opacity-50 disabled:cursor-not-allowed text-amber-400 border border-amber-500/30 rounded-lg transition-colors min-h-[44px]"
          >
            In Progress
          </button>

          <button
            type="button"
            disabled={isUpdatingStatus || pothole.status === "resolved"}
            onClick={() => handleStatusChange("resolved")}
            className="px-2.5 py-2 text-xs font-medium bg-emerald-500/10 hover:bg-emerald-500/20 disabled:opacity-50 disabled:cursor-not-allowed text-emerald-400 border border-emerald-500/30 rounded-lg transition-colors min-h-[44px]"
          >
            Resolved
          </button>
        </div>

        {pothole.reportStatus === "failed" ? (
          <button
            type="button"
            disabled={isGeneratingReport}
            onClick={handleGenerateReport}
            className="w-full mt-2 flex items-center justify-center gap-2 px-3 py-2 text-xs font-semibold bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white rounded-lg transition-colors min-h-[44px]"
          >
            <Send className="w-3.5 h-3.5" />
            <span>{isGeneratingReport ? "Retrying Report..." : "Retry Report"}</span>
          </button>
        ) : (
          <div className="mt-2 p-2.5 bg-slate-950/70 border border-slate-800 rounded-lg text-xs flex items-center justify-between">
            <span className="text-slate-400">Incident Ticket:</span>
            <span className="font-semibold text-emerald-400">
              {pothole.reportStatus === "sent"
                ? "Email sent successfully"
                : pothole.reportStatus === "simulated"
                ? "Demo report generated"
                : "Dashboard ticket created"}
            </span>
          </div>
        )}
      </div>

      {/* Status History Timeline */}
      {pothole.statusHistory && pothole.statusHistory.length > 0 && (
        <div className="border-t border-slate-800 pt-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300 mb-2">
            <History className="w-3.5 h-3.5 text-slate-400" />
            <span>Audit History ({pothole.statusHistory.length})</span>
          </div>

          <div className="space-y-2 max-h-36 overflow-y-auto pr-1">
            {pothole.statusHistory.map((item, idx) => (
              <div
                key={idx}
                className="text-[11px] p-2 bg-slate-950/70 border border-slate-800 rounded-md"
              >
                <div className="flex items-center justify-between text-slate-400">
                  <span className="font-semibold text-slate-200 capitalize">
                    {item.status.replace("_", " ")}
                  </span>
                  <span>{new Date(item.changedAt).toLocaleTimeString()}</span>
                </div>
                {item.note && <p className="text-slate-400 mt-0.5">{item.note}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
