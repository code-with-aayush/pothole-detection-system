# Product Requirements Document: PotholeAlert

## 1. Product overview

Build a working full-stack prototype called PotholeAlert.

The product detects potholes from a mobile camera frame or uploaded image, attaches GPS coordinates and timestamp, estimates severity, identifies the responsible civic authority, creates a report, and displays all reported potholes on an operations dashboard.

This is an internship assignment prototype. Prioritize a complete and reliable end-to-end flow over production-scale complexity.

The primary demo flow is:

Camera or image upload
→ pothole detection
→ GPS coordinate capture
→ address lookup
→ authority assignment
→ pothole saved to MongoDB
→ report generated
→ pothole appears on Leaflet dashboard
→ operator updates status

## 2. Required technology

Frontend:
- Next.js 14 or newer
- App Router
- TypeScript
- Tailwind CSS
- Leaflet and react-leaflet
- Responsive mobile-first interface

Backend:
- Python
- FastAPI
- Ultralytics YOLO
- Pillow
- MongoDB with PyMongo or Motor
- Nodemailer is optional on the frontend; preferably implement email through a backend SMTP service

Machine learning:
- Use the model:
  Harisanth/Pothole-Finetuned-YOLOv8
- Download the best.pt file through a script
- Store the model locally under backend/models/best.pt
- Do not commit large model weights to Git if avoidable
- Include model download instructions in the README

Maps:
- Leaflet
- OpenStreetMap tiles
- Do not require Google Maps API keys

Geocoding:
- Use Nominatim reverse geocoding
- Add a User-Agent header
- Cache results where practical
- If geocoding fails, still save coordinates and show “Address unavailable”

Database:
- MongoDB
- Support MONGODB_URI through environment variables
- Add a simple seed script for demo data

## 3. Scope

### P0 must-have features

1. Image upload detection
2. Mobile rear-camera capture
3. GPS capture
4. YOLO pothole detection
5. Bounding box and confidence
6. Severity estimate
7. Authority assignment
8. MongoDB persistence
9. Report creation
10. Leaflet dashboard
11. Status updates
12. README
13. Demo mode when email is not configured

### P1 features if time remains

1. Wake Lock API
2. PWA manifest
3. Frame capture every three seconds
4. Duplicate detection within 50 meters and 10 seconds
5. Camera bounding-box overlay
6. Email delivery through SMTP
7. Landscape orientation prompt
8. Status history timeline

### Explicitly out of scope

- User authentication
- Payment functionality
- Nationwide authority data
- Real government API integration
- SMS
- Video file storage
- Road ownership machine learning
- Pothole depth measurement
- Offline synchronization
- Complex admin roles
- Advanced analytics

## 4. User roles

### Driver

Can:
- Open the camera page
- Grant camera and location access
- Start detection
- See current coordinates
- See detection feedback
- Stop detection
- Upload a test image as fallback

### Operator

Can:
- View all reported potholes
- Filter by severity
- Filter by status
- View pothole details
- View evidence image
- View assigned authority
- Change status

There is no authentication in this prototype.

## 5. Frontend pages

### Page 1: Detection page

Route:
- `/detect`

Requirements:
- Rear camera by default using facingMode environment
- Start Detection button
- Stop Detection button
- Upload Test Image button
- Video preview
- GPS coordinates at the top
- Current address if available
- Current detection status
- Latest severity alert
- Last reported count
- Landscape-mode warning
- Camera and location permission error states
- Wake Lock while detection is active if browser supports it

Camera behavior:
- Capture one frame every three seconds
- Compress images to JPEG quality 0.6
- Send image plus GPS to backend
- Prevent multiple requests from running simultaneously
- Stop all intervals and tracks when detection stops

### Page 2: Dashboard

Route:
- `/dashboard`

Requirements:
- Leaflet map
- Pothole markers
- Marker color based on severity/status
- Pothole list
- Severity filter
- Status filter
- Authority filter
- Click marker to open detail panel
- Refresh button
- Status update control

### Page 3: Pothole details

Can be a modal or side panel.

Show:
- Evidence image
- Detection confidence
- Severity
- Coordinates
- Address
- Timestamp
- Assigned authority
- Report status
- Current status
- Status history
- Buttons for status updates

## 6. Backend endpoints

### GET /health

Response:

{
  "status": "ok"
}

### POST /api/detect

Accept multipart form data.

Fields:
- file: image file
- latitude: optional number
- longitude: optional number
- timestamp: optional ISO timestamp
- source: optional string

Behavior:
1. Validate image.
2. Run YOLO inference.
3. Use confidence threshold 0.28 initially.
4. Return detected bounding boxes.
5. If no pothole is detected, return detected false.
6. If a pothole is detected and coordinates exist:
   - reverse geocode
   - identify authority
   - check duplicate
   - save record
   - create report
7. Return the saved pothole ID.

Example response:

{
  "detected": true,
  "potholeId": "id",
  "confidence": 0.82,
  "severity": "high",
  "bbox": {
    "x1": 100,
    "y1": 80,
    "x2": 430,
    "y2": 290
  },
  "authority": "MCD",
  "reportStatus": "simulated"
}

### GET /api/potholes

Support query parameters:
- status
- severity
- authority
- limit

Return potholes sorted newest first.

### GET /api/potholes/{id}

Return one pothole with status history.

### PATCH /api/potholes/{id}/status

Request:

{
  "status": "in_progress",
  "note": "Road crew assigned"
}

Allowed statuses:
- reported
- acknowledged
- in_progress
- resolved

Append every status update to statusHistory.

### POST /api/potholes/{id}/report

Create or resend a report.

If SMTP is configured:
- send an email

If SMTP is not configured:
- set reportStatus to simulated
- save the report payload
- return a successful response

## 7. Database schema

Create a potholes collection with records shaped like:

{
  "_id": "...",
  "latitude": 28.6139,
  "longitude": 77.2090,
  "address": "Readable address",
  "imageUrl": "optional local or data URL",
  "detectedAt": "ISO date",
  "confidence": 0.82,
  "severity": "high",
  "authority": {
    "name": "Municipal Corporation of Delhi",
    "shortName": "MCD",
    "email": "demo-mcd@example.com"
  },
  "status": "reported",
  "reportStatus": "simulated",
  "reportPayload": {},
  "source": "mobile_camera",
  "statusHistory": [
    {
      "status": "reported",
      "changedAt": "ISO date",
      "note": "Created by detection"
    }
  ],
  "createdAt": "ISO date",
  "updatedAt": "ISO date"
}

Add indexes for:
- detectedAt
- status
- severity
- latitude and longitude if practical

## 8. Authority mapping

Create:

backend/data/authorities.json

Use a small Delhi NCR demonstration dataset.

Each authority should contain:
- name
- shortName
- email
- bounds or polygon
- optional road patterns

Example:

{
  "name": "Municipal Corporation of Delhi",
  "shortName": "MCD",
  "email": "demo-mcd@example.com",
  "bounds": {
    "minLat": 28.45,
    "maxLat": 28.88,
    "minLng": 76.84,
    "maxLng": 77.35
  }
}

Implement a service:

get_authority_for_location(latitude, longitude)

If there is no match, return:
- name: "Unassigned"
- shortName: "UNKNOWN"

Document in the README that the authority mapping is seeded prototype data and should be replaced by official GIS road ownership data in production.

## 9. Severity logic

The model only detects potholes and does not measure physical depth.

Implement a transparent prototype heuristic:
- high if confidence >= 0.75 or bounding-box area is large
- medium if confidence >= 0.50 or bounding-box area is moderate
- low otherwise

Document this limitation in the README.

## 10. Duplicate detection

Before creating a new record:
- compare the new coordinates with recent potholes
- if an existing pothole is within 50 meters
- and it was detected within the last 10 seconds
- return the existing record instead of creating a duplicate

If GPS is missing, skip duplicate detection.

## 11. Reporting behavior

Build a report payload with:
- authority
- coordinates
- address
- severity
- confidence
- detected timestamp
- evidence image reference
- dashboard URL if available

Support two modes:

SMTP mode:
- use environment variables
- send a real test email

Demo mode:
- do not fail if SMTP is absent
- store the payload
- set reportStatus to simulated
- show this clearly in the interface

Never hardcode credentials.
Never commit secrets.
Create `.env.example`.

## 12. Environment variables

Create `.env.example`:

MONGODB_URI=
MONGODB_DB_NAME=pothole_alert
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
REPORT_FROM_EMAIL=
NEXT_PUBLIC_API_URL=http://localhost:8000

## 13. Error handling

Handle:
- invalid image
- model failure
- no detection
- camera permission denial
- location permission denial
- geocoding failure
- MongoDB failure
- SMTP failure
- duplicate detection
- network timeout

The user should receive readable error messages, not raw stack traces.

## 14. Seed data

Create a seed script that inserts at least five potholes:
- two high severity
- two medium severity
- one resolved
- different authorities
- realistic Delhi NCR coordinates

The dashboard must look useful on first launch.

## 15. Development commands

The README must include:

Frontend:
npm install
npm run dev

Backend:
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

Model:
python scripts/download_model.py

Seed:
python scripts/seed_data.py

## 16. Acceptance criteria

The implementation is complete when:

1. The backend health endpoint works.
2. A pothole test image returns a detection.
3. A normal image returns no detection or a low-confidence result.
4. A detected pothole with GPS is saved to MongoDB.
5. An authority is assigned.
6. A report is generated.
7. Demo mode works without SMTP credentials.
8. The dashboard displays markers.
9. Filters work.
10. A pothole status can be changed.
11. The mobile page opens the rear camera.
12. The mobile page captures and submits frames.
13. GPS permission errors are handled.
14. The README explains setup and limitations.
15. The project can be demonstrated without hidden manual database steps.

## 17. Implementation discipline

Build in this order:

1. Backend health endpoint
2. Model download and image inference
3. Database connection
4. Authority mapping
5. Detection-to-database pipeline
6. Reporting service
7. Dashboard
8. Image upload fallback
9. Mobile camera
10. Wake Lock and PWA polish
11. Testing and README

After each step:
- run the relevant command
- fix errors immediately
- do not move ahead with broken core functionality

Do not add authentication, SMS, cloud video storage, or complex GIS unless all acceptance criteria are complete.