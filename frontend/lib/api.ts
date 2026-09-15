import { Pothole, Status } from "@/types/pothole";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export function getFullImageUrl(relativePath?: string): string {
  if (!relativePath) return "";
  if (relativePath.startsWith("http://") || relativePath.startsWith("https://")) {
    return relativePath;
  }
  const cleanPath = relativePath.startsWith("/") ? relativePath : `/${relativePath}`;
  return `${API_BASE}${cleanPath}`;
}

export async function fetchPotholes(params?: {
  status?: string;
  severity?: string;
  authority?: string;
  limit?: number;
  includeDemo?: boolean;
}): Promise<Pothole[]> {
  const query = new URLSearchParams();
  if (params?.status && params.status !== "all") query.set("status", params.status);
  if (params?.severity && params.severity !== "all") query.set("severity", params.severity);
  if (params?.authority && params.authority !== "all") query.set("authority", params.authority);
  if (params?.limit) query.set("limit", String(params.limit));

  // Default includeDemo to false to show live-only incidents
  const includeDemo = params?.includeDemo !== undefined ? params.includeDemo : false;
  query.set("includeDemo", String(includeDemo));

  const url = `${API_BASE}/api/potholes${query.toString() ? `?${query.toString()}` : ""}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch incidents (${res.status} ${res.statusText})`);
  }
  return res.json();
}

export async function fetchPotholeById(id: string): Promise<Pothole> {
  const res = await fetch(`${API_BASE}/api/potholes/${encodeURIComponent(id)}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Incident #${id} not found (${res.status})`);
  }
  return res.json();
}

export async function updatePotholeStatus(
  id: string,
  newStatus: Status,
  note = ""
): Promise<Pothole> {
  const res = await fetch(`${API_BASE}/api/potholes/${encodeURIComponent(id)}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: newStatus, note }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Status update failed (${res.status})`);
  }
  return res.json();
}

export async function generatePotholeReport(id: string): Promise<{
  success: boolean;
  simulated: boolean;
  reportStatus: string;
  message: string;
  pothole: Pothole;
}> {
  const res = await fetch(`${API_BASE}/api/potholes/${encodeURIComponent(id)}/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Report generation failed (${res.status})`);
  }
  return res.json();
}

export async function ingestPotholeDetection(formData: FormData): Promise<import("@/types/pothole").IngestResponse> {
  const res = await fetch(`${API_BASE}/api/detections/ingest`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Automatic ingestion failed (${res.status})`);
  }
  return res.json();
}

interface AuthorityCacheEntry {
  data: {
    authority: { name: string; shortName: string; email: string };
    address: string;
  };
  expiresAt: number;
}

const AUTHORITY_CACHE_TTL_MS = 60_000; // 60 seconds
const authorityCache = new Map<string, AuthorityCacheEntry>();

function authorityKey(lat: number, lng: number): string {
  return `${lat.toFixed(4)},${lng.toFixed(4)}`;
}

export async function fetchAuthority(
  latitude: number,
  longitude: number
): Promise<{
  authority: { name: string; shortName: string; email: string };
  address: string;
}> {
  const key = authorityKey(latitude, longitude);
  const cached = authorityCache.get(key);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.data;
  }

  const query = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
  });
  const res = await fetch(`${API_BASE}/api/authority?${query.toString()}`);
  if (!res.ok) {
    return {
      authority: {
        name: "Unassigned Road Authority",
        shortName: "UNKNOWN",
        email: "unassigned@example.com",
      },
      address: "",
    };
  }
  const data = await res.json();
  authorityCache.set(key, { data, expiresAt: Date.now() + AUTHORITY_CACHE_TTL_MS });
  return data;
}

