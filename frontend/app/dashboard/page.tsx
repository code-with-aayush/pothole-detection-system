"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Pothole } from "@/types/pothole";
import { fetchPotholes } from "@/lib/api";
import { StatsCards } from "@/components/StatsCards";
import { FilterBar } from "@/components/FilterBar";
import { PotholeList } from "@/components/PotholeList";
import { PotholeDetail } from "@/components/PotholeDetail";
import { Navbar } from "@/components/Navbar";

// Dynamically import Leaflet map with SSR disabled to prevent window is not defined errors
const PotholeMap = dynamic(
  () => import("@/components/PotholeMap").then((mod) => mod.PotholeMap),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-[350px] md:h-[520px] rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center text-slate-500 text-xs animate-pulse">
        Loading Operations Map...
      </div>
    ),
  }
);

export default function DashboardPage() {
  const [potholes, setPotholes] = useState<Pothole[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filters
  const [selectedSeverity, setSelectedSeverity] = useState("all");
  const [selectedStatus, setSelectedStatus] = useState("all");
  const [selectedAuthority, setSelectedAuthority] = useState("all");

  // Selected incident for detail panel
  const [selectedPotholeId, setSelectedPotholeId] = useState<string | undefined>(undefined);

  const loadIncidents = useCallback(async () => {
    try {
      const data = await fetchPotholes({ includeDemo: false });
      setErrorMessage(null);
      // Strictly filter out any demo or seeded records so only real data is present
      const realData = data.filter(
        (p) => !p.isDemo && p.source !== "seed_demo" && !p.seedKey
      );
      setPotholes(realData);

      // Check if URL specifies a selected incident ID
      const urlParams = new URLSearchParams(window.location.search);
      const paramSelected = urlParams.get("selected");

      if (paramSelected && realData.some((p) => p._id === paramSelected)) {
        setSelectedPotholeId(paramSelected);
      } else if (realData.length > 0 && !selectedPotholeId) {
        setSelectedPotholeId(realData[0]._id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load incidents";
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [selectedPotholeId]);

  useEffect(() => {
    let ignore = false;
    const init = async () => {
      await loadIncidents();
      if (ignore) return;
    };
    init();
    return () => {
      ignore = true;
    };
  }, [loadIncidents]);

  const handleManualRefresh = () => {
    setIsRefreshing(true);
    loadIncidents();
  };

  // Filtered incidents based on active dropdowns
  const filteredPotholes = useMemo(() => {
    return potholes.filter((p) => {
      const matchSeverity = selectedSeverity === "all" || p.severity === selectedSeverity;
      const matchStatus = selectedStatus === "all" || p.status === selectedStatus;
      const matchAuthority =
        selectedAuthority === "all" ||
        p.authority?.shortName?.toUpperCase() === selectedAuthority.toUpperCase();
      return matchSeverity && matchStatus && matchAuthority;
    });
  }, [potholes, selectedSeverity, selectedStatus, selectedAuthority]);

  const selectedPothole = useMemo(() => {
    return potholes.find((p) => p._id === selectedPotholeId) || null;
  }, [potholes, selectedPotholeId]);

  const handleUpdatePothole = (updated: Pothole) => {
    setPotholes((prev) =>
      prev.map((item) => (item._id === updated._id ? updated : item))
    );
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-amber-500/20 selection:text-amber-300">
      <Navbar activeIncidentsCount={potholes.length} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-4 sm:px-6 sm:py-6 space-y-4 sm:space-y-6">
        {/* Dashboard Title & Quick Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
          <div>
            <h1 className="text-lg font-bold text-white flex items-center gap-2">
              <span>Road Maintenance Operations Feed</span>
              <span className="px-2 py-0.5 text-xs font-mono font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded">
                Live Data Active
              </span>
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Verified road hazard tickets and prototype department routing
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleManualRefresh}
              disabled={isRefreshing}
              className="flex items-center gap-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 active:bg-slate-900 border border-slate-700 text-slate-200 text-xs font-semibold rounded-xl transition-colors min-h-[42px] cursor-pointer"
              title="Refresh incident list"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-amber-400" : ""}`} />
              <span>Refresh Feed</span>
            </button>
          </div>
        </div>
        {/* Error Alert Banner */}
        {errorMessage && (
          <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-center justify-between gap-3 text-rose-300 text-xs">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{errorMessage}. Ensure the FastAPI backend is running on port 8000.</span>
            </div>
            <button
              onClick={handleManualRefresh}
              className="px-3 py-1.5 bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-white rounded-lg font-medium transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* 4 Metric Cards */}
        <StatsCards
          potholes={potholes}
          onSelectMetric={(key) => {
            if (key === "all") {
              setSelectedSeverity("all");
              setSelectedStatus("all");
              setSelectedAuthority("all");
            } else if (key === "high") {
              setSelectedSeverity("high");
              setSelectedStatus("all");
              setSelectedAuthority("all");
            } else {
              setSelectedSeverity("all");
              setSelectedStatus(key);
              setSelectedAuthority("all");
            }
          }}
        />

        {/* Filter Controls */}
        <FilterBar
          selectedSeverity={selectedSeverity}
          onSelectSeverity={setSelectedSeverity}
          selectedStatus={selectedStatus}
          onSelectStatus={setSelectedStatus}
          selectedAuthority={selectedAuthority}
          onSelectAuthority={setSelectedAuthority}
          matchingCount={filteredPotholes.length}
        />

        {/* Responsive Two-Column Operations Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 sm:gap-6 items-start">
          {/* Left Column: Interactive Leaflet Map (7 cols on desktop) */}
          <div className="lg:col-span-7 flex flex-col gap-2">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-400 px-1">
              <span>Delhi NCR Geographic Coverage</span>
              <span className="text-[11px] text-slate-500">
                {filteredPotholes.filter((p) => p.latitude !== null).length} mapped markers
              </span>
            </div>
            <PotholeMap
              potholes={filteredPotholes}
              selectedPotholeId={selectedPotholeId}
              onSelectPothole={(p) => setSelectedPotholeId(p._id)}
            />
          </div>

          {/* Right Column: Incident List & Detail Panel (5 cols on desktop) */}
          <div className="lg:col-span-5 flex flex-col gap-4">
            {selectedPothole ? (
              <PotholeDetail
                pothole={selectedPothole}
                onClose={() => setSelectedPotholeId(undefined)}
                onUpdatePothole={handleUpdatePothole}
              />
            ) : null}

            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Incident Feed
                </h3>
                <span className="text-[11px] text-slate-500">
                  {filteredPotholes.length} total
                </span>
              </div>

              <PotholeList
                potholes={filteredPotholes}
                selectedPotholeId={selectedPotholeId}
                onSelectPothole={(p) => setSelectedPotholeId(p._id)}
                isLoading={isLoading}
              />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
