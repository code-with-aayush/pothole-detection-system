"""
PotholeAlert — CLI test runner for the YOLO model.

Usage:
  python scripts/test_model.py <image_path>

Loads backend/models/best.pt, runs inference, prints results,
and saves an annotated image under backend/runs/.
"""

import sys
from pathlib import Path

# Ensure backend/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.detection import detect_potholes, get_model, CONFIDENCE_THRESHOLD
from PIL import Image
from ultralytics import YOLO


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_model.py <image_path>")
        sys.exit(1)

    image_path = Path(sys.argv[1])
    if not image_path.exists():
        print(f"ERROR: Image not found at {image_path}")
        sys.exit(1)

    print(f"Loading image: {image_path}")
    image = Image.open(image_path).convert("RGB")
    print(f"Image size: {image.width}x{image.height}")

    # --- Service-level detection ---
    print(f"\nRunning detection (confidence threshold = {CONFIDENCE_THRESHOLD}) …")
    detections = detect_potholes(image)

    if not detections:
        print("Result: No potholes detected.")
    else:
        print(f"Result: {len(detections)} pothole(s) detected\n")
        for i, det in enumerate(detections, 1):
            print(f"  Detection {i}:")
            print(f"    Confidence : {det['confidence']:.4f}")
            print(f"    Severity   : {det['severity']}")
            b = det["bbox"]
            print(f"    BBox       : ({b['x1']:.0f}, {b['y1']:.0f}) → ({b['x2']:.0f}, {b['y2']:.0f})")

    # --- Save annotated image via Ultralytics ---
    runs_dir = Path(__file__).resolve().parent.parent / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    model = get_model()
    results = model.predict(
        source=str(image_path),
        conf=CONFIDENCE_THRESHOLD,
        save=True,
        project=str(runs_dir),
        name="test",
        exist_ok=True,
    )

    output_path = runs_dir / "test" / image_path.name
    if output_path.exists():
        print(f"\nAnnotated image saved to: {output_path}")
    else:
        # Ultralytics may name it differently
        test_dir = runs_dir / "test"
        saved = list(test_dir.glob("*")) if test_dir.exists() else []
        if saved:
            print(f"\nAnnotated image(s) in: {test_dir}")
            for f in saved:
                print(f"  {f}")
        else:
            print(f"\nAnnotated output directory: {test_dir} (check for saved images)")


if __name__ == "__main__":
    main()
