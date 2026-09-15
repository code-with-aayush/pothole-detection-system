export type Severity = "low" | "medium" | "high";
export type Status = "reported" | "acknowledged" | "in_progress" | "resolved";
export type ReportStatus =
  | "pending"
  | "dashboard_ticket_created"
  | "sent"
  | "simulated"
  | "failed"
  | "unreported"
  | "queued";

export interface Authority {
  name: string;
  shortName: string;
  email?: string;
}

export interface BBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface StatusHistoryEntry {
  status: string;
  changedAt: string;
  note?: string;
}

export interface Pothole {
  _id: string;
  latitude: number | null;
  longitude: number | null;
  address?: string;
  imageUrl?: string;
  detectedAt: string;
  confidence: number;
  severity: Severity;
  authority: Authority;
  status: Status;
  reportStatus: ReportStatus;
  reportChannel?: string;
  reportPayload?: Record<string, unknown>;
  reportAttempts?: number;
  lastReportAttemptAt?: string | null;
  reportedAt?: string | null;
  lastDetectedAt?: string;
  detectionCount?: number;
  source?: string;
  isDemo?: boolean;
  bbox?: BBox;
  statusHistory?: StatusHistoryEntry[];
  createdAt?: string;
  updatedAt?: string;
  seedKey?: string;
  reportData?: Record<string, unknown>;
}

export interface IngestResponse {
  detected: boolean;
  potholeId?: string;
  isDuplicate?: boolean;
  authority?: Authority;
  severity?: Severity;
  confidence?: number;
  status?: Status;
  reportStatus?: ReportStatus;
  reportChannel?: string;
  coordinates?: {
    latitude: number;
    longitude: number;
  };
  imageUrl?: string;
  address?: string;
  detectionCount?: number;
  lastDetectedAt?: string;
  message: string;
}

export interface FilterState {
  severity: string;
  status: string;
}
