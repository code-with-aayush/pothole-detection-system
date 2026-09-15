"""
PotholeAlert — Model download script.

Downloads the YOLOv8 pothole detection model from HuggingFace:
  Harisanth/Pothole-Finetuned-YOLOv8

Saves the best.pt weights to  backend/models/best.pt
"""

import sys
from pathlib import Path

REPO_ID = "Harisanth/Pothole-Finetuned-YOLOv8"
FILENAME = "best.pt"
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


def download_model() -> Path:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("ERROR: huggingface-hub is not installed. Run:")
        print("  pip install huggingface-hub")
        sys.exit(1)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = MODELS_DIR / FILENAME

    if dest.exists():
        print(f"Model already exists at {dest}")
        return dest

    print(f"Downloading {FILENAME} from {REPO_ID} …")
    downloaded_path = hf_hub_download(
        repo_id=REPO_ID,
        filename=FILENAME,
        local_dir=str(MODELS_DIR),
        local_dir_use_symlinks=False,
    )
    print(f"Downloaded to {downloaded_path}")

    final = MODELS_DIR / FILENAME
    if not final.exists():
        downloaded = Path(downloaded_path)
        downloaded.rename(final)

    print(f"Model ready at {final}")
    return final


if __name__ == "__main__":
    download_model()
