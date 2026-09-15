"""
PotholeAlert — Detection service.

Loads the YOLOv8 pothole model and provides inference + severity estimation.
"""

from pathlib import Path
from typing import TypedDict

from PIL import Image
from ultralytics import YOLO

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "best.pt"
CONFIDENCE_THRESHOLD = 0.28

# Bounding-box area thresholds (fraction of image area) for severity heuristic
_LARGE_AREA_FRAC = 0.10
_MODERATE_AREA_FRAC = 0.03


class BBox(TypedDict):
    x1: float
    y1: float
    x2: float
    y2: float


class Detection(TypedDict):
    detected: bool
    confidence: float
    severity: str
    bbox: BBox


_model: YOLO | None = None


def get_model() -> YOLO:
    """Lazy-load the YOLO model (singleton)."""
    global _model
    if _model is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model weights not found at {MODEL_PATH}. "
                "Run: python scripts/download_model.py"
            )
        _model = YOLO(str(MODEL_PATH))
    return _model


def estimate_severity(confidence: float, bbox: BBox, image_area: float) -> str:
    """
    Transparent prototype heuristic (see PRD §9).

    - high:   confidence >= 0.75  OR  bbox area >= 10% of image
    - medium: confidence >= 0.50  OR  bbox area >= 3% of image
    - low:    everything else
    """
    bbox_area = max(0, (bbox["x2"] - bbox["x1"]) * (bbox["y2"] - bbox["y1"]))
    area_frac = bbox_area / image_area if image_area > 0 else 0

    if confidence >= 0.75 or area_frac >= _LARGE_AREA_FRAC:
        return "high"
    if confidence >= 0.50 or area_frac >= _MODERATE_AREA_FRAC:
        return "medium"
    return "low"


def detect_potholes(image: Image.Image) -> list[Detection]:
    """
    Run inference on a PIL Image.

    Returns a list of Detection dicts (one per detected pothole).
    Empty list means no pothole found above threshold.
    """
    model = get_model()
    results = model.predict(source=image, conf=CONFIDENCE_THRESHOLD, verbose=False)

    image_area = image.width * image.height
    detections: list[Detection] = []

    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue
        for box in boxes:
            conf = float(box.conf[0])
            x1, y1, x2, y2 = [float(c) for c in box.xyxy[0]]
            bbox: BBox = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
            severity = estimate_severity(conf, bbox, image_area)
            detections.append(
                Detection(
                    detected=True,
                    confidence=round(conf, 4),
                    severity=severity,
                    bbox=bbox,
                )
            )

    return detections
