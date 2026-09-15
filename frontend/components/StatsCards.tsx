"use client";

import { AlertTriangle, CheckCircle2, Clock, MapPin } from "lucide-react";
import { Pothole } from "@/types/pothole";

interface StatsCardsProps {
  potholes: Pothole[];
  onSelectMetric?: (filterType: "all" | "reported" | "high" | "resolved") => void;
}

export function StatsCards({ potholes, onSelectMetric }: StatsCardsProps) {
  const total = potholes.length;
  const reported = potholes.filter((p) => p.status === "reported").length;
  const highSeverity = potholes.filter((p) => p.severity === "high").length;
  const resolved = potholes.filter((p) => p.status === "resolved").length;

  const cards = [
    {
      label: "Total Incidents",
      count: total,
      subtext: "Logged across Delhi NCR",
      icon: MapPin,
      borderColor: "border-slate-800",
      textColor: "text-white",
      iconBg: "bg-slate-800/60 text-slate-300",
      filterKey: "all" as const,
    },
    {
      label: "Reported / Pending",
      count: reported,
      subtext: "Awaiting authority action",
      icon: Clock,
      borderColor: "border-amber-500/30",
      textColor: "text-amber-400",
      iconBg: "bg-amber-500/10 text-amber-400",
      filterKey: "reported" as const,
    },
    {
      label: "High Severity",
      count: highSeverity,
      subtext: "Critical road surface damage",
      icon: AlertTriangle,
      borderColor: "border-rose-500/30",
      textColor: "text-rose-400",
      iconBg: "bg-rose-500/10 text-rose-400",
      filterKey: "high" as const,
    },
    {
      label: "Resolved",
      count: resolved,
      subtext: "Patched & closed by crews",
      icon: CheckCircle2,
      borderColor: "border-emerald-500/30",
      textColor: "text-emerald-400",
      iconBg: "bg-emerald-500/10 text-emerald-400",
      filterKey: "resolved" as const,
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <button
            key={card.label}
            type="button"
            onClick={() => onSelectMetric?.(card.filterKey)}
            className={`flex flex-col justify-between p-4 bg-slate-900/90 border ${card.borderColor} rounded-xl text-left hover:border-slate-700 transition-all cursor-pointer min-h-[44px]`}
          >
            <div className="flex items-center justify-between w-full mb-2">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                {card.label}
              </span>
              <div className={`p-1.5 rounded-md ${card.iconBg}`}>
                <Icon className="w-4 h-4" />
              </div>
            </div>
            <div>
              <div className={`text-2xl sm:text-3xl font-extrabold tracking-tight ${card.textColor}`}>
                {card.count}
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5 truncate">
                {card.subtext}
              </p>
            </div>
          </button>
        );
      })}
    </div>
  );
}
