"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldAlert, Camera, LayoutDashboard } from "lucide-react";

interface NavbarProps {
  activeIncidentsCount?: number;
}

export function Navbar({ activeIncidentsCount }: NavbarProps) {
  const pathname = usePathname();
  const isScanner = pathname === "/" || pathname === "/detect";
  const isDashboard = pathname.startsWith("/dashboard");

  return (
    <header className="border-b border-slate-800 bg-slate-950/90 backdrop-blur-md px-4 py-3 sm:px-6 sticky top-0 z-40">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 max-w-7xl mx-auto">
        {/* Brand identity */}
        <Link href="/" className="flex items-center gap-3 group">
          <div className="p-2 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-400 group-hover:bg-amber-500/20 transition-all shadow-sm">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold tracking-tight text-white group-hover:text-amber-300 transition-colors">
                PotholeAlert
              </span>
              <span className="px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-slate-800 text-amber-400 border border-slate-700 rounded">
                Delhi NCR
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Civic AI Road Hazard Detection &amp; Authority Dispatch
            </p>
          </div>
        </Link>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-2 self-stretch sm:self-center">
          <nav className="flex items-center p-1 bg-slate-900 border border-slate-800 rounded-xl w-full sm:w-auto">
            <Link
              href="/"
              className={`flex-1 sm:flex-none flex items-center justify-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg transition-all min-h-[40px] ${
                isScanner
                  ? "bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
              }`}
            >
              <Camera className="w-4 h-4" />
              <span>Live Scanner</span>
              {isScanner && (
                <span className="w-2 h-2 rounded-full bg-slate-950 animate-pulse" />
              )}
            </Link>

            <Link
              href="/dashboard"
              className={`flex-1 sm:flex-none flex items-center justify-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg transition-all min-h-[40px] ${
                isDashboard
                  ? "bg-slate-800 text-white border border-slate-700 shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
              }`}
            >
              <LayoutDashboard className="w-4 h-4" />
              <span>Operations Dashboard</span>
              {typeof activeIncidentsCount === "number" && (
                <span className="px-1.5 py-0.2 text-[10px] font-mono font-bold bg-slate-700/80 text-amber-300 rounded-full">
                  {activeIncidentsCount}
                </span>
              )}
            </Link>
          </nav>
        </div>
      </div>
    </header>
  );
}
