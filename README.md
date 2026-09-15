# Smart Pothole Detection & Reporting System

A full-stack application that detects potholes in real time from mobile camera or dashcam feeds, attaches GPS coordinates and timestamps, resolves the responsible civic authority (MCD, PWD, NHAI), and logs incident tickets to an operations dashboard with automated reporting.

Built as an end-to-end prototype using a fine-tuned YOLOv8 computer vision model, FastAPI, Next.js, Leaflet maps, and MongoDB.

---

## How It Works

1. **Live Camera Feed & Detection**: The web app mounts a mobile rear-camera or dashcam feed (using the browser's MediaDevices API) and samples frames at 3-second intervals. There is also a file upload fallback for testing with pre-recorded photos.
2. **YOLOv8 Inference**: Frames are sent to the FastAPI backend, which runs inference using a fine-tuned YOLOv8 model from Hugging Face (`Harisanth/Pothole-Finetuned-YOLOv8`). Potholes are tagged with bounding boxes, confidence scores, and rough severity ratings.
3. **Location & Geocoding**: Each detection captures GPS coordinates from the device and reverse-geocodes them into a readable street address using OpenStreetMap Nominatim.
4. **Authority Assignment**: Based on the location coordinates and road classification (highway, ring road, or municipal colony street), the system identifies the jurisdiction responsible for road repair:
   - **NHAI**: National Highways and Expressways
   - **PWD**: State highways, arterial ring roads, and major flyovers
   - **MCD**: Local municipal roads, colony streets, and civic ward infrastructure
5. **Deduplication (50-Meter Buffer)**: To avoid filing duplicate tickets for the same pothole as a vehicle drives by, the backend checks for existing unresolved potholes within a 50-meter radius. If found, the existing incident's detection count is incremented and timestamp refreshed rather than cluttering the database with duplicate records.
6. **Automated Incident Reporting**: On a verified new detection, an incident ticket is immediately created in MongoDB, the evidence snapshot is saved, and a report is dispatched (via SMTP email if configured, or in simulation mode with complete audit history).
7. **Operations Dashboard**: Municipal road crews and operators can track all incidents on an interactive Leaflet map, filter by authority, severity, or status, inspect photos and coordinates, and advance tickets through their lifecycle: `Reported` → `Acknowledged` → `In Progress` → `Resolved`.

---

## Tech Stack & Libraries

- **Frontend**: Next.js 14+ (App Router), React 19, TypeScript, Tailwind CSS
- **Maps**: Leaflet + `react-leaflet` with OpenStreetMap tiles (no third-party API key required)
- **Backend**: Python 3.11+, FastAPI, Uvicorn, PyMongo, Pillow
- **Computer Vision**: Ultralytics YOLOv8 (`Harisanth/Pothole-Finetuned-YOLOv8` via Hugging Face Hub)
- **Database**: MongoDB (indexes on timestamps, severity, status, and coordinates)
- **Geocoding**: OpenStreetMap Nominatim API (with custom User-Agent and caching)
- **Email / Dispatch**: Python `smtplib` + email MIME generation (with demo simulation fallback)
- **Testing**: pytest, HTTPX / Starlette TestClient (44 automated tests)

---

## Project Structure

```
├── backend/
│   ├── main.py                     # FastAPI routes & pipeline coordination
│   ├── db.py                       # MongoDB connection & index configuration
│   ├── models/
│   │   ├── pothole.py              # Pydantic schemas, validation & doc builders
│   │   └── best.pt                 # YOLOv8 fine-tuned weights (downloaded via script)
│   ├── repositories/
│   │   └── pothole_repository.py   # MongoDB queries & 50m spatial deduplication
│   ├── services/
│   │   ├── detection.py            # YOLO inference wrapper & severity heuristic
│   │   ├── geocoding.py            # Nominatim reverse geocoder
│   │   ├── authority.py            # Civic authority resolution logic
│   │   ├── reporting.py            # SMTP dispatch & ticket generator
│   │   └── geo.py                  # Haversine distance calculator
│   ├── data/
│   │   └── authorities.json        # Delhi NCR jurisdictional data & bounds
│   ├── scripts/
│   │   ├── download_model.py       # Hugging Face model weight downloader
│   │   ├── check_db.py             # Database connectivity test
│   │   ├── reset_db.py             # Clean database utility
│   │   └── seed_data.py            # Optional sample data for quick demos
│   ├── tests/                      # Automated unit and API test suite
│   ├── requirements.txt            # Python dependencies
│   └── .env.example                # Backend environment template
├── frontend/
│   ├── app/
│   │   ├── page.tsx                # Landing route (redirects to /detect)
│   │   ├── detect/page.tsx         # Real-time camera scanner & upload fallback
│   │   ├── dashboard/page.tsx      # Operations dashboard & ticket feed
│   │   ├── manifest.ts             # PWA web manifest
│   │   └── layout.tsx
│   ├── components/
│   │   ├── PotholeMap.tsx          # Leaflet map with color-coded severity markers
│   │   ├── PotholeList.tsx         # Incident feed with search & status badges
│   │   ├── PotholeDetail.tsx       # Incident inspection, photo & status updater
│   │   ├── FilterBar.tsx           # Severity, status, and authority dropdown filters
│   │   ├── StatsCards.tsx          # High-level metric summary cards
│   │   └── Navbar.tsx              # Top navigation header
│   ├── lib/
│   │   └── api.ts                  # Typed client for backend REST endpoints
│   └── types/
│       └── pothole.ts              # Shared frontend TypeScript interfaces
└── sample-data/                    # Sample road photos for testing upload fallback
```

---

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Node.js 18+ and npm
- MongoDB running locally on port 27017 (or a MongoDB Atlas connection string)

### 1. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On macOS/Linux:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download model weights from Hugging Face (~6MB)
python scripts/download_model.py

# Configure environment
cp .env.example .env
```

The default `.env` is configured for local development:
```env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=pothole_alert
# Optional: fill these only if you want real outgoing email dispatch
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
REPORT_FROM_EMAIL=
```

Start the FastAPI server:
```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive API documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Frontend Setup

In a second terminal window:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## How to Test & Demo

1. **Live Camera Scanner (`/detect`)**:
   - Open [http://localhost:3000/detect](http://localhost:3000/detect) on a phone or laptop.
   - Grant camera and location permissions.
   - Click **Start Camera** to begin real-time road scanning. The app captures frames every 3 seconds, displays GPS telemetry, draws bounding boxes around detected potholes, and automatically files tickets.
   - If testing indoors without a road feed, click **Upload Photo Fallback** and select one of the test images from the `sample-data/` folder.
2. **Check Automatic Ticket Creation**:
   - As soon as a pothole is detected, you will see the detected severity, assigned authority (e.g., PWD or MCD), and the generated ticket confirmation card.
3. **Operations Dashboard (`/dashboard`)**:
   - Navigate to [http://localhost:3000/dashboard](http://localhost:3000/dashboard).
   - View all plotted potholes on the Leaflet map with color-coded severity markers (Red = High, Amber = Medium, Blue = Low, Green = Resolved).
   - Test the filters: filter by **Authority** (MCD / PWD / NHAI), **Severity**, or **Status**.
   - Click on any incident to open the detail panel, review the photo evidence, and click the status buttons to move it from `Reported` → `Acknowledged` → `In Progress` → `Resolved`. Notice the audit history updates automatically.

---

## Running Automated Tests

The test suite covers the complete pipeline: model inference, Nominatim geocoding, authority matching, spatial deduplication within 50m, MongoDB operations, and status workflows.

```bash
cd backend
pytest tests/ -v
```

All 44 tests should pass cleanly.

---

## Engineering Design & Trade-offs

- **Two-Tier Endpoint Architecture**: Instead of writing to MongoDB and firing alerts on every single camera frame, the frontend hits a lightweight inference endpoint (`POST /api/infer`) during continuous scanning. The heavy ingestion pipeline (`POST /api/detections/ingest`) is only triggered when a positive detection with GPS occurs, keeping network overhead low.
- **50-Meter Spatial Deduplication**: When vehicles travel over damaged asphalt, the camera captures multiple consecutive frames of the same hole. The backend checks existing open tickets using the Haversine formula; if an incident already exists within 50 meters, it increments the detection counter and logs the timestamp without creating redundant tickets.
- **Severity Heuristics**: Computer vision models detect 2D bounding boxes; they cannot measure physical pothole depth from a single monocular camera. Our severity heuristic combines model confidence score with the bounding box area relative to the frame (boxes covering ≥10% or confidence ≥75% are classified as High severity). In a commercial deployment, this would be paired with vehicle accelerometer/gyroscope spikes or stereo depth cameras.
- **Authority Mapping**: Implemented for Delhi NCR using a hybrid approach: road name/type keyword matching takes first priority (National Highways → NHAI, Ring Roads/Flyovers → PWD, colony and ward streets → MCD), backed by bounding coordinate boxes for fallback. In production, this can be swapped with GIS polygon overlays from municipal shapefiles.
- **Reporting Flexibility**: If SMTP credentials are provided, the system sends an email to the authority with the image, coordinates, and Google Maps link. If running in demo mode without SMTP credentials, it logs a simulated report payload and creates a dashboard ticket without failing or halting execution.

---

## Prototype Simplifications vs. Production Plan

To keep this project completely self-contained and runnable on any reviewer's machine without private government API keys or paid third-party subscriptions, a few parts currently use prototype stand-ins. Here is what is simplified today and how each piece would work in a real-world production deployment:

1. **Authority Contacts & Mapping**
   - **Current Prototype**: Uses `backend/data/authorities.json` with demo contact emails (`demo-mcd@example.com`, etc.) and rectangular bounding boxes covering Delhi NCR.
   - **In Production**: We would query official municipal GIS layers (such as Delhi GSDI) using PostGIS spatial polygon queries to pinpoint the exact administrative ward, zonal division, and executive engineer responsible for that specific road segment.

2. **Civic Department Reporting**
   - **Current Prototype**: Creates an internal dashboard ticket and dispatches the alert via standard SMTP email (or realistic simulation mode if SMTP credentials are left blank).
   - **In Production**: We would integrate directly with official civic grievance systems (e.g. MCD 311 API, Delhi PWD Sewa portal, CPGRAMS, or NHAI Sukhad Yatra) using authenticated REST endpoints or webhook callbacks.

3. **Pothole Depth & Severity**
   - **Current Prototype**: A single monocular camera only captures 2D images, so depth cannot be physically measured. Severity is estimated through a heuristic combining model confidence with bounding-box area relative to the frame.
   - **In Production**: We would use sensor fusion by correlating camera detections with vehicle telematics (reading Z-axis accelerometer spikes from the phone or vehicle OBD-II/CAN bus) or by using stereo depth cameras to calculate the true physical depth and crater volume.

4. **Inference Location & Data Bandwidth**
   - **Current Prototype**: The frontend captures frames and streams them over HTTP to the FastAPI server for inference every 3 seconds.
   - **In Production**: For vehicles moving on cellular networks, running inference directly on the edge device (using ONNX Runtime Web, TensorFlow Lite, or CoreML) is far more efficient. Only positive detections and cropped evidence photos would be transmitted over 4G/5G, saving over 95% of data bandwidth.

5. **Evidence Photo Storage**
   - **Current Prototype**: Snapshot photos are saved to the local filesystem (`backend/uploads/`) and served statically.
   - **In Production**: Snapshots would be pushed directly to cloud object storage (AWS S3 or Google Cloud Storage) using presigned upload URLs and served through a CDN (CloudFront or Cloudflare).

6. **Authentication & Access Control**
   - **Current Prototype**: Open access without login barriers so evaluators can test both the scanner and the operations dashboard immediately.
   - **In Production**: Role-based access control (RBAC). Drivers and dashcam devices authenticate via hardware API keys, while municipal road crews log in to accounts scoped strictly to their assigned zone or ward.

---

## Production Cloud Deployment

For deploying this system to production:

- **Frontend**: Deploy the Next.js app to **Vercel** or **AWS Amplify** with edge caching.
- **Backend**: Containerize the FastAPI app with Docker and host on **Google Cloud Run** or **AWS ECS Fargate**.
- **Model Storage**: Pre-bake model weights into the container image or pull from an **AWS S3** bucket during startup.
- **Database**: Use managed **MongoDB Atlas** with automated backups and read replicas.
- **Photo Evidence**: Store uploaded evidence snapshots in an **S3 / Cloud Storage** bucket fronted by a CDN (CloudFront / Cloudflare).

