"use client";

import {
  useRef,
  useState,
  useCallback,
  useEffect,
  type ChangeEvent,
} from "react";
import Link from "next/link";
import {
  Camera,
  CameraOff,
  Upload,
  MapPin,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  SwitchCamera,
  ExternalLink,
  Building2,
  Mail,
  RefreshCw,
  Clock,
  ShieldCheck,
} from "lucide-react";
import { fetchAuthority, ingestPotholeDetection, generatePotholeReport } from "@/lib/api";
import { Navbar } from "@/components/Navbar";

const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

function calculateDistanceMeters(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371e3;
  const rad1 = (lat1 * Math.PI) / 180;
  const rad2 = (lat2 * Math.PI) / 180;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(rad1) * Math.cos(rad2) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface BBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

interface Detection {
  detected: boolean;
  confidence: number;
  severity: string;
  bbox: BBox;
}

interface AuthorityMeta {
  name: string;
  shortName: string;
  email: string;
  description?: string;
}

interface InferResponse {
  detected: boolean;
  detections: Detection[];
  count: number;
  imageWidth: number;
  imageHeight: number;
}

interface GpsCoords {
  latitude: number;
  longitude: number;
  accuracy: number;
}

interface ActiveCandidate {
  frameId: string;
  blob: Blob;
  detectedAt: string;
  confidence: number;
  severity: string;
  count: number;
  reported: boolean;
  source: "mobile_camera" | "upload";
  authority?: AuthorityMeta | null;
  address?: string;
}

interface ReportOutcome {
  success: boolean;
  isDuplicate: boolean;
  potholeId: string;
  authorityName: string;
  authorityEmail?: string;
  reportStatus: "simulated" | "sent" | "failed" | "dashboard_ticket_created" | string;
  message: string;
  imageUrl?: string;
  address?: string;
}

const SEVERITY_COLORS: Record<string, string> = {
  high: "#ef4444",
  medium: "#f59e0b",
  low: "#22c55e",
};

const CAPTURE_INTERVAL_MS = 3000;
const JPEG_QUALITY = 0.6;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */
export default function DetectPage() {
  // Camera refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Ingestion refs & throttle
  const isIngestingRef = useRef(false);
  const lastIngestTimeRef = useRef<number>(0);
  const lastIngestCoordsRef = useRef<{ lat: number; lng: number } | null>(null);
  const lastIngestedPotholeIdRef = useRef<string | null>(null);

  // State
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [facingMode, setFacingMode] = useState<"environment" | "user">("environment");
  const [isInferring, setIsInferring] = useState(false);
  const [gps, setGps] = useState<GpsCoords | null>(null);
  const [gpsError, setGpsError] = useState<string | null>(null);
  const [assignedAuthority, setAssignedAuthority] = useState<AuthorityMeta | null>(null);
  const [geocodedAddress, setGeocodedAddress] = useState<string>("");
  const [lastInferTime, setLastInferTime] = useState<string | null>(null);
  const [frameCount, setFrameCount] = useState(0);
  const [totalDetections, setTotalDetections] = useState(0);

  // Reporting candidate and outcome state
  const [activeCandidate, setActiveCandidate] = useState<ActiveCandidate | null>(null);
  const [isSubmittingReport, setIsSubmittingReport] = useState(false);
  const [isRetryingReport, setIsRetryingReport] = useState(false);
  const [ingestStatus, setIngestStatus] = useState<
    "idle" | "detected" | "saving" | "created" | "sent" | "simulated" | "failed"
  >("idle");
  const [reportError, setReportError] = useState<string | null>(null);
  const [reportOutcome, setReportOutcome] = useState<ReportOutcome | null>(null);

  // Upload fallback
  const [uploadResult, setUploadResult] = useState<InferResponse | null>(null);
  const [uploadPreviewUrl, setUploadPreviewUrl] = useState<string | null>(null);
  const [isUploadInferring, setIsUploadInferring] = useState(false);

  /* ---------------------------------------------------------------- */
  /*  GPS Telemetry & Department Resolution                           */
  /* ---------------------------------------------------------------- */
  useEffect(() => {
    if (!("geolocation" in navigator)) {
      queueMicrotask(() => {
        setGpsError("Geolocation not available");
      });
      return;
    }
    const watchId = navigator.geolocation.watchPosition(
      async (pos) => {
        const coords: GpsCoords = {
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        };
        setGps(coords);
        setGpsError(null);

        // Resolve assigned road department for current coordinates
        try {
          const authData = await fetchAuthority(coords.latitude, coords.longitude);
          if (authData?.authority) {
            setAssignedAuthority(authData.authority);
          }
          if (authData?.address) {
            setGeocodedAddress(authData.address);
          }
        } catch {
          // Keep existing or fallback
        }
      },
      (err) => {
        setGpsError(err.message);
      },
      { enableHighAccuracy: true, maximumAge: 10000, timeout: 15000 }
    );
    return () => navigator.geolocation.clearWatch(watchId);
  }, []);

  /* ---------------------------------------------------------------- */
  /*  Wake Lock                                                        */
  /* ---------------------------------------------------------------- */
  useEffect(() => {
    let wakeLock: WakeLockSentinel | null = null;
    async function requestWakeLock() {
      try {
        if ("wakeLock" in navigator && cameraActive) {
          wakeLock = await navigator.wakeLock.request("screen");
        }
      } catch {
        /* ignore */
      }
    }
    requestWakeLock();
    return () => {
      wakeLock?.release().catch(() => {});
    };
  }, [cameraActive]);

  /* ---------------------------------------------------------------- */
  /* ---------------------------------------------------------------- */
  /*  Automatic Ingestion (POST /api/detections/ingest)               */
  /* ---------------------------------------------------------------- */
  const triggerAutoIngest = useCallback(
    async (blob: Blob, source: "mobile_camera" | "upload") => {
      // Prevent overlapping ingestion requests
      if (isIngestingRef.current) return;

      // Require valid GPS coordinates
      if (!gps || typeof gps.latitude !== "number" || typeof gps.longitude !== "number") {
        setGpsError("Valid GPS coordinates required for automatic incident ticket creation.");
        return;
      }

      const now = Date.now();
      // Client-side deduplication protection: wait at least 30 seconds before attempting another ingestion for the same area (< 50m)
      if (lastIngestCoordsRef.current) {
        const dist = calculateDistanceMeters(
          gps.latitude,
          gps.longitude,
          lastIngestCoordsRef.current.lat,
          lastIngestCoordsRef.current.lng
        );
        if (dist < 50 && now - lastIngestTimeRef.current < 30000) {
          return;
        }
      }

      isIngestingRef.current = true;
      setIsSubmittingReport(true);
      setReportError(null);
      setIngestStatus("saving");

      try {
        const form = new FormData();
        form.append("file", blob, "camera_frame.jpg");
        form.append("latitude", String(gps.latitude));
        form.append("longitude", String(gps.longitude));
        form.append("source", source);
        form.append("timestamp", new Date().toISOString());

        const res = await ingestPotholeDetection(form);

        if (!res.detected) {
          setIngestStatus("idle");
          return;
        }

        lastIngestTimeRef.current = Date.now();
        lastIngestCoordsRef.current = { lat: gps.latitude, lng: gps.longitude };
        lastIngestedPotholeIdRef.current = res.potholeId ?? null;

        if (res.reportStatus === "sent") {
          setIngestStatus("sent");
        } else if (res.reportStatus === "simulated") {
          setIngestStatus("simulated");
        } else if (res.reportStatus === "failed") {
          setIngestStatus("failed");
        } else {
          setIngestStatus("created");
        }

        setReportOutcome({
          success: res.reportStatus !== "failed",
          isDuplicate: !!res.isDuplicate,
          potholeId: res.potholeId || "",
          authorityName: res.authority?.name || "Assigned Road Department",
          authorityEmail: res.authority?.email,
          reportStatus: res.reportStatus || "dashboard_ticket_created",
          message: res.isDuplicate
            ? "Duplicate detection merged into existing dashboard ticket"
            : res.reportStatus === "sent"
            ? "Email sent successfully"
            : res.reportStatus === "simulated"
            ? "Dashboard ticket created; email simulation mode active"
            : res.reportStatus === "failed"
            ? "Dashboard ticket created, but email delivery failed"
            : "Dashboard ticket created",
          imageUrl: res.imageUrl,
          address: res.address,
        });
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Automatic incident ingestion failed";
        setReportError(msg);
        setIngestStatus("failed");
      } finally {
        isIngestingRef.current = false;
        setIsSubmittingReport(false);
      }
    },
    [gps]
  );

  /* ---------------------------------------------------------------- */
  /*  Draw bounding boxes on overlay canvas                            */
  /* ---------------------------------------------------------------- */
  const drawOverlay = useCallback((data: InferResponse) => {
    const overlay = overlayRef.current;
    const video = videoRef.current;
    if (!overlay || !video) return;

    const displayW = video.clientWidth;
    const displayH = video.clientHeight;
    overlay.width = displayW;
    overlay.height = displayH;

    const ctx = overlay.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, displayW, displayH);

    if (!data.detected || data.detections.length === 0) return;

    const scaleX = displayW / data.imageWidth;
    const scaleY = displayH / data.imageHeight;

    for (const det of data.detections) {
      const color = SEVERITY_COLORS[det.severity] || "#f59e0b";
      const x1 = det.bbox.x1 * scaleX;
      const y1 = det.bbox.y1 * scaleY;
      const w = (det.bbox.x2 - det.bbox.x1) * scaleX;
      const h = (det.bbox.y2 - det.bbox.y1) * scaleY;

      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.strokeRect(x1, y1, w, h);

      const label = `${det.severity.toUpperCase()} ${(det.confidence * 100).toFixed(0)}%`;
      ctx.font = "bold 14px monospace";
      const metrics = ctx.measureText(label);
      const labelH = 20;
      ctx.fillStyle = color;
      ctx.fillRect(x1, y1 - labelH, metrics.width + 8, labelH);

      ctx.fillStyle = "#fff";
      ctx.fillText(label, x1 + 4, y1 - 5);
    }
  }, []);

  /* ---------------------------------------------------------------- */
  /*  Inference (send frame to backend)                                */
  /* ---------------------------------------------------------------- */
  const sendFrameForInference = useCallback(async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0);

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob((b) => resolve(b), "image/jpeg", JPEG_QUALITY)
    );
    if (!blob) return;

    setIsInferring(true);
    try {
      const form = new FormData();
      form.append("file", blob, "frame.jpg");

      const res = await fetch(`${API_BASE}/api/infer`, {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Inference failed (${res.status})`);
      }

      const data: InferResponse = await res.json();
      const currentTimeStr = new Date().toLocaleTimeString();
      setLastInferTime(currentTimeStr);
      setFrameCount((c) => c + 1);

      if (data.detected && data.detections.length > 0) {
        setTotalDetections((t) => t + data.count);
        const best = data.detections.reduce((a, b) =>
          a.confidence > b.confidence ? a : b
        );

        setIngestStatus((prev) => (prev === "idle" ? "detected" : prev));

        // Store candidate frame with identified department
        setActiveCandidate({
          frameId: `frame_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
          blob,
          detectedAt: new Date().toISOString(),
          confidence: best.confidence,
          severity: best.severity,
          count: data.count,
          reported: false,
          source: "mobile_camera",
          authority: assignedAuthority,
          address: geocodedAddress,
        });

        // Trigger automatic ingestion without requiring a manual button click
        triggerAutoIngest(blob, "mobile_camera");
      } else {
        // Road clear: clear candidate only if not actively ingesting
        if (!isIngestingRef.current) {
          setActiveCandidate(null);
          setIngestStatus("idle");
        }
      }

      drawOverlay(data);
    } catch {
      // Error handled by isInferring state reset; detection overlay cleared
    } finally {
      setIsInferring(false);
    }
  }, [assignedAuthority, geocodedAddress, triggerAutoIngest, drawOverlay]);

  /* ---------------------------------------------------------------- */
  /*  Start / Stop Camera                                              */
  /* ---------------------------------------------------------------- */
  const startCamera = useCallback(async () => {
    setCameraError(null);
    setReportOutcome(null);
    setReportError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode,
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraActive(true);

      // Start capture loop
      intervalRef.current = setInterval(() => {
        sendFrameForInference();
      }, CAPTURE_INTERVAL_MS);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Camera access denied";
      setCameraError(message);
    }
  }, [facingMode, sendFrameForInference]);

  const stopCamera = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
    setActiveCandidate(null);

    const overlay = overlayRef.current;
    if (overlay) {
      const ctx = overlay.getContext("2d");
      ctx?.clearRect(0, 0, overlay.width, overlay.height);
    }
  }, []);

  const switchCamera = useCallback(() => {
    const nextFacing = facingMode === "environment" ? "user" : "environment";
    setFacingMode(nextFacing);
    if (cameraActive) {
      stopCamera();
      setTimeout(() => {
        startCamera();
      }, 300);
    }
  }, [facingMode, cameraActive, stopCamera, startCamera]);

  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, [stopCamera]);

  /* ---------------------------------------------------------------- */
  /*  Manual Retry Report (Active only if report delivery failed)     */
  /* ---------------------------------------------------------------- */
  const handleRetryReport = async () => {
    const potholeId = reportOutcome?.potholeId || lastIngestedPotholeIdRef.current;
    if (!potholeId || isRetryingReport) return;

    setIsRetryingReport(true);
    setReportError(null);

    try {
      const res = await generatePotholeReport(potholeId);
      if (res.pothole) {
        const status = res.pothole.reportStatus || (res.success ? "sent" : "failed");
        setIngestStatus(status === "sent" ? "sent" : status === "simulated" ? "simulated" : "created");
        setReportOutcome((prev) =>
          prev
            ? {
                ...prev,
                success: res.success,
                reportStatus: status,
                message: res.message || (res.success ? "Email sent successfully" : "Report delivery failed"),
              }
            : null
        );
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to retry report";
      setReportError(msg);
    } finally {
      setIsRetryingReport(false);
    }
  };

  /* ---------------------------------------------------------------- */
  /*  Upload fallback                                                  */
  /* ---------------------------------------------------------------- */
  const handleUpload = useCallback(
    async (e: ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      const previewUrl = URL.createObjectURL(file);
      setUploadPreviewUrl(previewUrl);
      setUploadResult(null);
      setIsUploadInferring(true);
      setReportOutcome(null);
      setReportError(null);

      try {
        const form = new FormData();
        form.append("file", file);

        const res = await fetch(`${API_BASE}/api/infer`, {
          method: "POST",
          body: form,
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Inference failed (${res.status})`);
        }

        const data: InferResponse = await res.json();
        setUploadResult(data);

        if (data.detected && data.detections.length > 0) {
          const best = data.detections.reduce((a, b) =>
            a.confidence > b.confidence ? a : b
          );
          setActiveCandidate({
            frameId: `upload_${Date.now()}`,
            blob: file,
            detectedAt: new Date().toISOString(),
            confidence: best.confidence,
            severity: best.severity,
            count: data.count,
            reported: false,
            source: "upload",
            authority: assignedAuthority,
            address: geocodedAddress,
          });
          setIngestStatus("detected");
          triggerAutoIngest(file, "upload");
        } else {
          setActiveCandidate(null);
          setIngestStatus("idle");
        }
      } catch {
      // Error handled by upload result reset
        setUploadResult(null);
      } finally {
        setIsUploadInferring(false);
      }
    },
    [assignedAuthority, geocodedAddress, triggerAutoIngest]
  );

  /* ---------------------------------------------------------------- */
  /*  Draw upload result overlay                                       */
  /* ---------------------------------------------------------------- */
  const uploadCanvasRef = useRef<HTMLCanvasElement>(null);
  const uploadImgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    if (!uploadResult || !uploadPreviewUrl) return;
    const img = uploadImgRef.current;
    const canvas = uploadCanvasRef.current;
    if (!img || !canvas) return;

    const draw = () => {
      const displayW = img.clientWidth;
      const displayH = img.clientHeight;
      canvas.width = displayW;
      canvas.height = displayH;

      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      ctx.clearRect(0, 0, displayW, displayH);

      if (!uploadResult.detected) return;

      const scaleX = displayW / uploadResult.imageWidth;
      const scaleY = displayH / uploadResult.imageHeight;

      for (const det of uploadResult.detections) {
        const color = SEVERITY_COLORS[det.severity] || "#f59e0b";
        const x1 = det.bbox.x1 * scaleX;
        const y1 = det.bbox.y1 * scaleY;
        const w = (det.bbox.x2 - det.bbox.x1) * scaleX;
        const h = (det.bbox.y2 - det.bbox.y1) * scaleY;

        ctx.strokeStyle = color;
        ctx.lineWidth = 3;
        ctx.strokeRect(x1, y1, w, h);

        const label = `${det.severity.toUpperCase()} ${(det.confidence * 100).toFixed(0)}%`;
        ctx.font = "bold 14px monospace";
        const metrics = ctx.measureText(label);
        const labelH = 20;
        ctx.fillStyle = color;
        ctx.fillRect(x1, y1 - labelH, metrics.width + 8, labelH);
        ctx.fillStyle = "#fff";
        ctx.fillText(label, x1 + 4, y1 - 5);
      }
    };

    if (img.complete) {
      draw();
    } else {
      img.onload = draw;
    }
    window.addEventListener("resize", draw);
    return () => window.removeEventListener("resize", draw);
  }, [uploadResult, uploadPreviewUrl]);

  const hasValidGps = gps !== null && typeof gps.latitude === "number" && typeof gps.longitude === "number";
  const displayAuthority = activeCandidate?.authority || assignedAuthority;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-amber-500/20 selection:text-amber-300">
      {/* Unified App Navigation Bar */}
      <Navbar />

      {/* Main Scanner Experience */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-4 sm:px-6 sm:py-6 flex flex-col lg:flex-row gap-6">
        {/* -------------------------------------------------------- */}
        {/*  Left Column: Camera Viewport & Live Stream Controls      */}
        {/* -------------------------------------------------------- */}
        <section className="flex-1 flex flex-col gap-4">
          {/* Header banner with quick telemetry status */}
          <div className="flex items-center justify-between bg-slate-900/60 border border-slate-800 rounded-xl px-4 py-2.5">
            <div className="flex items-center gap-2 text-xs">
              <span className="flex h-2 w-2 relative">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${cameraActive ? "bg-emerald-400" : "bg-slate-500"}`} />
                <span className={`relative inline-flex rounded-full h-2 w-2 ${cameraActive ? "bg-emerald-500" : "bg-slate-600"}`} />
              </span>
              <span className="font-semibold text-slate-200">
                {cameraActive ? "Real-time AI Vision Active" : "Camera Standby"}
              </span>
              <span className="text-slate-500 hidden sm:inline">•</span>
              <span className="text-slate-400 hidden sm:inline">
                YOLOv8 Road Analysis Model
              </span>
            </div>

            {hasValidGps ? (
              <div className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-[11px] text-emerald-400 font-mono">
                <MapPin className="w-3 h-3" />
                <span>{gps?.latitude.toFixed(4)}, {gps?.longitude.toFixed(4)}</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 px-2.5 py-1 bg-amber-500/10 border border-amber-500/20 rounded-lg text-[11px] text-amber-400">
                <MapPin className="w-3 h-3" />
                <span>{gpsError || "Locating GPS..."}</span>
              </div>
            )}
          </div>

          {/* Camera Viewport */}
          <div className="relative bg-slate-900 rounded-2xl overflow-hidden border border-slate-800 aspect-video shadow-2xl shadow-black/40 flex items-center justify-center">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`w-full h-full object-cover ${!cameraActive ? "hidden" : ""}`}
            />

            {/* Hidden canvas for frame capture */}
            <canvas ref={canvasRef} className="hidden" />

            {/* Overlay canvas for model bounding boxes */}
            <canvas
              ref={overlayRef}
              className={`absolute inset-0 w-full h-full pointer-events-none ${!cameraActive ? "hidden" : ""}`}
            />

            {/* Inference Status Pill */}
            {isInferring && cameraActive && (
              <div className="absolute top-3 right-3 flex items-center gap-2 px-3 py-1.5 bg-black/70 backdrop-blur-md rounded-xl text-xs text-amber-400 border border-amber-500/30 shadow-lg">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Evaluating road frame…</span>
              </div>
            )}

            {/* Standby UI when camera is stopped */}
            {!cameraActive && (
              <div className="flex flex-col items-center justify-center gap-4 p-6 text-center max-w-md">
                <div className="p-5 bg-amber-500/10 border border-amber-500/20 rounded-2xl text-amber-400 shadow-inner">
                  <Camera className="w-12 h-12" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-white">
                    Live Road Hazard Camera
                  </h2>
                  <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                    Point your device at the road ahead. The AI will detect potholes, estimate severity, identify the maintenance department, and prepare an official repair ticket.
                  </p>
                </div>
                {cameraError && (
                  <div className="flex items-center gap-2 px-3 py-2 bg-rose-500/10 border border-rose-500/20 rounded-xl text-xs text-rose-300">
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                    <span>{cameraError}</span>
                  </div>
                )}
                <button
                  id="btn-start-camera-hero"
                  onClick={startCamera}
                  className="flex items-center gap-2 px-6 py-3 bg-amber-500 hover:bg-amber-400 active:bg-amber-600 text-slate-950 font-bold text-sm rounded-xl transition-all shadow-lg shadow-amber-500/25 cursor-pointer min-h-[44px]"
                >
                  <Camera className="w-4 h-4" />
                  <span>Start Live Camera</span>
                </button>
              </div>
            )}
          </div>

          {/* Camera Controls Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-slate-900/50 border border-slate-800 rounded-xl">
            <div className="flex items-center gap-2">
              {cameraActive ? (
                <button
                  id="btn-stop-camera"
                  onClick={stopCamera}
                  className="flex items-center gap-2 px-4 py-2.5 bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/30 text-rose-300 font-semibold text-xs rounded-lg transition-colors min-h-[44px]"
                >
                  <CameraOff className="w-4 h-4" />
                  <span>Stop Camera</span>
                </button>
              ) : (
                <button
                  id="btn-start-camera"
                  onClick={startCamera}
                  className="flex items-center gap-2 px-4 py-2.5 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs rounded-lg transition-colors shadow-md shadow-amber-500/20 min-h-[44px]"
                >
                  <Camera className="w-4 h-4" />
                  <span>Start Camera</span>
                </button>
              )}

              <button
                id="btn-switch-camera"
                onClick={switchCamera}
                className="flex items-center gap-2 px-3.5 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-medium rounded-lg transition-colors min-h-[44px]"
                title="Toggle front/rear camera"
              >
                <SwitchCamera className="w-4 h-4" />
                <span className="hidden sm:inline">Switch Camera</span>
              </button>
            </div>

            <div className="flex items-center gap-2">
              <input
                ref={fileInputRef}
                id="input-upload-image"
                type="file"
                accept="image/*"
                onChange={handleUpload}
                className="hidden"
              />
              <button
                id="btn-upload-image"
                onClick={() => fileInputRef.current?.click()}
                className="flex items-center gap-2 px-3.5 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-medium rounded-lg transition-colors min-h-[44px]"
              >
                <Upload className="w-4 h-4 text-amber-400" />
                <span>Upload Photo Fallback</span>
              </button>
            </div>
          </div>

          {/* Upload Preview & Analysis Panel */}
          {uploadPreviewUrl && (
            <div className="bg-slate-900 rounded-2xl border border-slate-800 overflow-hidden shadow-lg">
              <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                  Uploaded Photo Analysis
                </h3>
                <button
                  onClick={() => {
                    setUploadPreviewUrl(null);
                    setUploadResult(null);
                    setActiveCandidate(null);
                    if (fileInputRef.current) fileInputRef.current.value = "";
                  }}
                  className="text-xs text-slate-400 hover:text-white transition-colors"
                >
                  Clear Photo
                </button>
              </div>

              <div className="relative">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  ref={uploadImgRef}
                  src={uploadPreviewUrl}
                  alt="Uploaded pothole preview"
                  className="w-full max-h-[380px] object-contain bg-black/40"
                />
                <canvas
                  ref={uploadCanvasRef}
                  className="absolute inset-0 w-full h-full pointer-events-none"
                  style={{ objectFit: "contain" }}
                />
                {isUploadInferring && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/50 backdrop-blur-sm">
                    <div className="flex items-center gap-2 px-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-amber-400 text-xs shadow-xl">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Running YOLO inference on image…
                    </div>
                  </div>
                )}
              </div>

              {uploadResult && (
                <div className="px-4 py-3 border-t border-slate-800 text-xs">
                  {uploadResult.detected ? (
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                      <div>
                        <p className="font-semibold text-amber-300">
                          {uploadResult.count} pothole{uploadResult.count > 1 ? "s" : ""} verified by AI
                        </p>
                        <div className="flex flex-wrap gap-2 mt-1.5">
                          {uploadResult.detections.map((d, i) => (
                            <span
                              key={i}
                              className="text-[11px] px-2 py-0.5 rounded-md border font-mono"
                              style={{
                                color: SEVERITY_COLORS[d.severity] || "#f59e0b",
                                borderColor: SEVERITY_COLORS[d.severity] || "#f59e0b",
                                backgroundColor: `${SEVERITY_COLORS[d.severity] || "#f59e0b"}15`,
                              }}
                            >
                              {d.severity.toUpperCase()} ({(d.confidence * 100).toFixed(1)}%)
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-emerald-400">
                      <CheckCircle2 className="w-4 h-4" />
                      No potholes detected in this image
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* -------------------------------------------------------- */}
          {/*  Official Report Outcome Card (Dispatched Confirmation)   */}
          {/* -------------------------------------------------------- */}
          {reportOutcome && (
            <div className="p-5 bg-gradient-to-b from-slate-900 to-slate-950 border border-amber-500/30 rounded-2xl space-y-4 shadow-xl shadow-amber-500/5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400">
                    <ShieldCheck className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">
                      {reportOutcome.isDuplicate
                        ? "Duplicate Detection Merged"
                        : "Dashboard Ticket Created"}
                    </h3>
                    <p className="text-xs text-slate-400 font-mono">
                      Ticket #{reportOutcome.potholeId.slice(-8)}
                    </p>
                  </div>
                </div>

                <span
                  className={`text-xs px-2.5 py-1 font-bold uppercase rounded-lg border font-mono ${
                    reportOutcome.reportStatus === "sent"
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                      : reportOutcome.reportStatus === "simulated"
                      ? "bg-blue-500/10 text-blue-400 border-blue-500/30"
                      : reportOutcome.reportStatus === "failed"
                      ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                      : "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                  }`}
                >
                  {reportOutcome.reportStatus === "simulated"
                    ? "Demo Report"
                    : reportOutcome.reportStatus === "sent"
                    ? "Email Sent"
                    : reportOutcome.reportStatus === "failed"
                    ? "Report Failed"
                    : "Ticket Created"}
                </span>
              </div>

              {/* Department and Location summary */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-1">
                  <div className="flex items-center gap-1.5 text-slate-400 text-[11px] font-semibold uppercase">
                    <Building2 className="w-3.5 h-3.5 text-amber-400" />
                    <span>Responsible Authority</span>
                  </div>
                  <p className="font-bold text-white">
                    {reportOutcome.authorityName}
                  </p>
                  {reportOutcome.authorityEmail && (
                    <p className="text-[11px] text-slate-400 font-mono flex items-center gap-1">
                      <Mail className="w-3 h-3 text-slate-500" />
                      {reportOutcome.authorityEmail}
                    </p>
                  )}
                </div>

                <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-1">
                  <div className="flex items-center gap-1.5 text-slate-400 text-[11px] font-semibold uppercase">
                    <MapPin className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Location Coordinates</span>
                  </div>
                  <p className="font-medium text-slate-200 line-clamp-1">
                    {reportOutcome.address || "Delhi NCR Roadway"}
                  </p>
                  <p className="text-[11px] text-slate-400 font-mono">
                    {gps ? `Lat: ${gps.latitude.toFixed(4)}, Lng: ${gps.longitude.toFixed(4)}` : "Verified GPS"}
                  </p>
                </div>
              </div>

              {/* Transmission note */}
              <div className="p-3 bg-slate-950/80 border border-slate-800/80 rounded-xl text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Report Status:</span>
                  <span className="font-bold text-amber-300">
                    {reportOutcome.reportStatus === "simulated"
                      ? "Demo report generated"
                      : reportOutcome.reportStatus === "sent"
                      ? "Email sent successfully"
                      : reportOutcome.reportStatus === "failed"
                      ? "Report failed"
                      : reportOutcome.isDuplicate
                      ? "Duplicate detection merged"
                      : "Dashboard ticket created"}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500">
                  {reportOutcome.message}
                </p>
              </div>

              {/* Action buttons */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <div className="flex items-center gap-2">
                  <Link
                    href={`/dashboard?selected=${encodeURIComponent(reportOutcome.potholeId)}`}
                    className="flex items-center gap-2 px-4 py-2.5 bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold rounded-xl transition-all shadow-md shadow-amber-500/20 min-h-[44px]"
                  >
                    <ExternalLink className="w-4 h-4" />
                    <span>View Incident in Dashboard</span>
                  </Link>

                  {reportOutcome.reportStatus === "failed" && (
                    <button
                      type="button"
                      onClick={handleRetryReport}
                      disabled={isRetryingReport}
                      className="flex items-center gap-2 px-3 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold rounded-xl transition-colors min-h-[44px]"
                    >
                      {isRetryingReport ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <RefreshCw className="w-4 h-4" />
                      )}
                      <span>Retry Report</span>
                    </button>
                  )}
                </div>

                <button
                  onClick={() => setReportOutcome(null)}
                  className="px-3 py-2 text-xs font-medium text-slate-400 hover:text-white transition-colors"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}
        </section>

        {/* -------------------------------------------------------- */}
        {/*  Right Column: Detection HUD & Dispatch Report Action     */}
        {/* -------------------------------------------------------- */}
        <aside className="w-full lg:w-96 flex flex-col gap-4">
          {/* -------------------------------------------------------- */}
          {/*  Active Pothole Detection & Department Assignment Card    */}
          {/* -------------------------------------------------------- */}
          {activeCandidate ? (
            <div className="bg-gradient-to-b from-amber-500/10 via-slate-900 to-slate-950 border border-amber-500/40 rounded-2xl p-5 space-y-4 shadow-xl shadow-amber-500/10">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 bg-amber-500/20 rounded-lg text-amber-400 animate-pulse">
                    <AlertTriangle className="w-4 h-4" />
                  </div>
                  <h2 className="text-xs font-bold uppercase tracking-wider text-amber-300">
                    Hazard Detected Ahead
                  </h2>
                </div>
                <span
                  className="text-xs font-bold uppercase px-2.5 py-0.5 rounded-md border font-mono"
                  style={{
                    color: SEVERITY_COLORS[activeCandidate.severity] || "#f59e0b",
                    borderColor: SEVERITY_COLORS[activeCandidate.severity] || "#f59e0b",
                    backgroundColor: `${SEVERITY_COLORS[activeCandidate.severity] || "#f59e0b"}15`,
                  }}
                >
                  {activeCandidate.severity} Priority
                </span>
              </div>

              {/* Department Jurisdiction Card (Highlighted as requested by user) */}
              <div className="p-3.5 bg-slate-950/90 border border-slate-800 rounded-xl space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase text-slate-400 tracking-wider flex items-center gap-1">
                    <Building2 className="w-3 h-3 text-amber-400" />
                    Responsible Authority
                  </span>
                  <span className="px-1.5 py-0.2 text-[10px] font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded">
                    {displayAuthority?.shortName || "MCD"}
                  </span>
                </div>

                <p className="text-sm font-bold text-white">
                  {displayAuthority?.name || "Municipal Corporation of Delhi (MCD)"}
                </p>

                <div className="text-[11px] text-slate-400 space-y-1">
                  <p className="flex items-center gap-1 text-slate-300">
                    <Mail className="w-3 h-3 text-slate-500" />
                    <span>{displayAuthority?.email || "demo-mcd@example.com"}</span>
                  </p>
                  <p className="text-slate-500 text-[10px]">
                    Jurisdiction: Ward road maintenance, asphalt surfacing &amp; civic corridor repair
                  </p>
                </div>
              </div>

              {/* Metrics Grid */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2.5 bg-slate-950/70 border border-slate-800/80 rounded-xl">
                  <span className="text-slate-400 block text-[10px] uppercase font-semibold">AI Confidence</span>
                  <span className="font-mono text-base font-bold text-white">
                    {(activeCandidate.confidence * 100).toFixed(1)}%
                  </span>
                </div>

                <div className="p-2.5 bg-slate-950/70 border border-slate-800/80 rounded-xl">
                  <span className="text-slate-400 block text-[10px] uppercase font-semibold">Severity</span>
                  <span
                    className="font-bold capitalize text-base"
                    style={{
                      color: SEVERITY_COLORS[activeCandidate.severity] || "#f59e0b",
                    }}
                  >
                    {activeCandidate.severity}
                  </span>
                </div>
              </div>

              {/* Location details */}
              <div className="p-2.5 bg-slate-950/70 border border-slate-800/80 rounded-xl text-xs space-y-1">
                <span className="text-slate-400 block text-[10px] uppercase font-semibold flex items-center gap-1">
                  <MapPin className="w-3 h-3 text-emerald-400" />
                  Location
                </span>
                <p className="text-slate-200 font-medium line-clamp-1">
                  {geocodedAddress || "Delhi NCR Roadway"}
                </p>
                <p className="text-[11px] text-slate-400 font-mono">
                  {hasValidGps
                    ? `${gps?.latitude.toFixed(6)}, ${gps?.longitude.toFixed(6)}`
                    : "Acquiring GPS coordinates..."}
                </p>
              </div>

              {/* Automated Ingestion & Reporting Status */}
              <div className="space-y-2 pt-1">
                {/* Status Indicator */}
                {isSubmittingReport ? (
                  <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-xs font-semibold text-amber-300 flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-amber-400 shrink-0" />
                    <span>Saving incident...</span>
                  </div>
                ) : ingestStatus === "sent" ? (
                  <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-xs font-semibold text-emerald-300 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Report sent</span>
                  </div>
                ) : ingestStatus === "simulated" ? (
                  <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-xl text-xs font-semibold text-blue-300 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-blue-400 shrink-0" />
                    <span>Demo report generated</span>
                  </div>
                ) : ingestStatus === "created" ? (
                  <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-xs font-semibold text-emerald-300 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Dashboard ticket created</span>
                  </div>
                ) : ingestStatus === "failed" ? (
                  <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs font-semibold text-rose-300 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                    <span>Report failed</span>
                  </div>
                ) : (
                  <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-xs font-semibold text-amber-300 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                    <span>Detection found</span>
                  </div>
                )}

                {/* Missing GPS warning if applicable */}
                {!hasValidGps && (
                  <div className="p-2.5 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-300 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
                    <span>GPS is required to assign road maintenance jurisdiction.</span>
                  </div>
                )}

                {/* Ingestion/Reporting error */}
                {reportError && (
                  <div className="p-2.5 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-300">
                    {reportError}
                  </div>
                )}

                {/* Action Buttons: Automated flow controls */}
                {isSubmittingReport ? (
                  <button
                    disabled
                    className="w-full flex items-center justify-center gap-2 px-4 py-3.5 rounded-xl text-xs font-bold bg-slate-800 text-slate-400 border border-slate-700 min-h-[48px] cursor-not-allowed"
                  >
                    <Loader2 className="w-4 h-4 animate-spin text-amber-400" />
                    <span>Report processing...</span>
                  </button>
                ) : reportOutcome?.potholeId ? (
                  <div className="space-y-2">
                    <div className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>
                        {reportOutcome.isDuplicate
                          ? "Duplicate detection merged"
                          : "Dashboard ticket created"}
                      </span>
                    </div>

                    {reportOutcome.reportStatus === "failed" && (
                      <button
                        type="button"
                        id="btn-retry-report"
                        onClick={handleRetryReport}
                        disabled={isRetryingReport}
                        className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white transition-colors cursor-pointer min-h-[44px]"
                      >
                        {isRetryingReport ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <RefreshCw className="w-4 h-4" />
                        )}
                        <span>Retry Report</span>
                      </button>
                    )}

                    <Link
                      id="btn-view-incident"
                      href={`/dashboard?selected=${encodeURIComponent(reportOutcome.potholeId)}`}
                      className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-xs font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 transition-colors shadow-lg shadow-amber-500/20 cursor-pointer min-h-[48px]"
                    >
                      <ExternalLink className="w-4 h-4" />
                      <span>View Incident</span>
                    </Link>
                  </div>
                ) : !hasValidGps ? (
                  <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl text-center text-xs text-slate-400 font-mono">
                    Acquiring GPS coordinates for automatic ticket creation...
                  </div>
                ) : (
                  <div className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-xs font-bold bg-slate-800/80 text-slate-400 border border-slate-700 min-h-[44px]">
                    <Clock className="w-4 h-4 text-amber-400" />
                    <span>Awaiting automatic ingestion...</span>
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* Standby HUD when no active pothole in frame */
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 text-center space-y-3">
              <div className="flex flex-col items-center justify-center py-4">
                {cameraActive ? (
                  <>
                    <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl text-emerald-400 mb-2">
                      <CheckCircle2 className="w-8 h-8" />
                    </div>
                    <p className="text-sm font-semibold text-white">
                      Road Surface Clear
                    </p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Scanning live video feed for asphalt depressions…
                    </p>
                  </>
                ) : (
                  <>
                    <div className="p-3 bg-slate-800 rounded-2xl text-slate-600 mb-2">
                      <XCircle className="w-8 h-8" />
                    </div>
                    <p className="text-sm font-semibold text-slate-300">
                      Vision Scanner Offline
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Activate camera to start real-time pothole tracking
                    </p>
                  </>
                )}
              </div>
            </div>
          )}

          {/* Session Telemetry & Statistics */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Scanner Telemetry
              </h3>
              <span className="text-[11px] text-slate-500 font-mono">
                Session Active
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <StatCard label="Frames Analyzed" value={String(frameCount)} />
              <StatCard label="Potholes Spotted" value={String(totalDetections)} />
              <StatCard
                label="Stream State"
                value={cameraActive ? "Live" : "Standby"}
                color={cameraActive ? "text-emerald-400" : "text-slate-500"}
              />
              <StatCard
                label="Last Evaluation"
                value={lastInferTime || "—"}
              />
            </div>
          </div>

          {/* Active Jurisdiction Overview */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 text-xs space-y-2.5">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5 text-amber-400" />
                <span>Delhi NCR Authorities</span>
              </h3>
            </div>
            <div className="space-y-1.5 text-[11px] text-slate-400">
              <div className="flex items-center justify-between p-2 bg-slate-950/60 rounded-lg border border-slate-800/80">
                <span className="font-semibold text-white">MCD</span>
                <span>Municipal &amp; Colony Roads</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-slate-950/60 rounded-lg border border-slate-800/80">
                <span className="font-semibold text-white">PWD</span>
                <span>Arterial Ring Roads &amp; Flyovers</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-slate-950/60 rounded-lg border border-slate-800/80">
                <span className="font-semibold text-white">NHAI</span>
                <span>National Highways &amp; Expressways</span>
              </div>
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Small stat card                                                    */
/* ------------------------------------------------------------------ */
function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="bg-slate-950/60 border border-slate-800 rounded-xl px-3 py-2">
      <p className="text-[10px] uppercase font-semibold text-slate-500">{label}</p>
      <p className={`text-sm font-bold ${color || "text-slate-200"}`}>
        {value}
      </p>
    </div>
  );
}
