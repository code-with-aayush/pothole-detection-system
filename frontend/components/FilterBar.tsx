"use client";

import { SlidersHorizontal } from "lucide-react";

interface FilterBarProps {
  selectedSeverity: string;
  onSelectSeverity: (val: string) => void;
  selectedStatus: string;
  onSelectStatus: (val: string) => void;
  selectedAuthority: string;
  onSelectAuthority: (val: string) => void;
  matchingCount: number;
}

export function FilterBar({
  selectedSeverity,
  onSelectSeverity,
  selectedStatus,
  onSelectStatus,
  selectedAuthority,
  onSelectAuthority,
  matchingCount,
}: FilterBarProps) {
  const hasActiveFilter =
    selectedSeverity !== "all" || selectedStatus !== "all" || selectedAuthority !== "all";

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-slate-900/60 border border-slate-800 rounded-xl">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
          <SlidersHorizontal className="w-3.5 h-3.5 text-slate-400" />
          <span>Filters:</span>
        </div>

        {/* Severity Filter */}
        <div className="flex items-center gap-1.5">
          <label htmlFor="severity-select" className="text-xs text-slate-400">
            Severity:
          </label>
          <select
            id="severity-select"
            value={selectedSeverity}
            onChange={(e) => onSelectSeverity(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-amber-500 min-h-[44px]"
          >
            <option value="all">All Severities</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        {/* Status Filter */}
        <div className="flex items-center gap-1.5">
          <label htmlFor="status-select" className="text-xs text-slate-400">
            Status:
          </label>
          <select
            id="status-select"
            value={selectedStatus}
            onChange={(e) => onSelectStatus(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-amber-500 min-h-[44px]"
          >
            <option value="all">All Statuses</option>
            <option value="reported">Reported</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="in_progress">In Progress</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>

        {/* Authority Filter */}
        <div className="flex items-center gap-1.5">
          <label htmlFor="authority-select" className="text-xs text-slate-400">
            Authority:
          </label>
          <select
            id="authority-select"
            value={selectedAuthority}
            onChange={(e) => onSelectAuthority(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-amber-500 min-h-[44px]"
          >
            <option value="all">All Authorities</option>
            <option value="MCD">MCD — Municipal Corporation</option>
            <option value="PWD">PWD — Public Works Dept</option>
            <option value="NHAI">NHAI — National Highways</option>
          </select>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-400">
          Showing <span className="font-semibold text-white">{matchingCount}</span> incidents
        </span>
        {hasActiveFilter && (
          <button
            type="button"
            onClick={() => {
              onSelectSeverity("all");
              onSelectStatus("all");
              onSelectAuthority("all");
            }}
            className="text-xs text-amber-400 hover:text-amber-300 underline underline-offset-2 min-h-[44px] flex items-center"
          >
            Reset
          </button>
        )}
      </div>
    </div>
  );
}
