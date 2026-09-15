"use client";

import Link from "next/link";
import { ShieldAlert, RefreshCw, Radio, Camera } from "lucide-react";

interface HeaderProps {
  onRefresh: () => void;
  isRefreshing: boolean;
  incidentCount: number;
}

export function Header({ onRefresh, isRefreshing, incidentCount }: HeaderProps) {
  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-md px-4 py-3 sm:px-6 sticky top-0 z-30">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 max-w-7xl mx-auto">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-400">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-white">
                PotholeAlert
              </h1>
              <span className="px-2 py-0.5 text-xs font-semibold uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700 rounded">
                Delhi NCR Ops
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Automated road hazard detection, authority dispatch &amp; maintenance tracking
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 self-end sm:self-center">
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-md text-xs text-slate-300">
            <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            <span>Active Feed: {incidentCount} recorded</span>
          </div>

          <Link
            href="/detect"
            className="flex items-center gap-2 px-3.5 py-2 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 text-xs font-medium rounded-lg transition-colors min-h-[44px]"
          >
            <Camera className="w-3.5 h-3.5" />
            <span>Live Detect</span>
          </Link>

          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 active:bg-slate-900 border border-slate-700 text-slate-200 text-xs font-medium rounded-lg transition-colors min-h-[44px]"
            title="Refresh active incidents"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-amber-400" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>
    </header>
  );
}
