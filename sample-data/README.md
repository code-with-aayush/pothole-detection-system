# Sample Data

Place test images here for pothole detection testing.

## Recommended test images

1. **pothole.jpg** — A real photo of a road with a visible pothole.  
   Use this to verify the YOLO model detects potholes correctly.

2. **clean_road.jpg** — A photo of a clean road with no damage.  
   Use this to verify the model returns no detections.

## Where to find test images

- Search "pothole road photo" on any stock image site  
- Take a photo of a real pothole with your phone  
- Use images from the [Pothole Detection Dataset on Kaggle](https://www.kaggle.com/datasets/atulyakumar98/pothole-detection-dataset)

## Usage

```bash
cd backend
python scripts/test_model.py ../sample-data/pothole.jpg
```

The annotated output will be saved to `backend/runs/test/`.
