# Smart Vision Assistant for Blind Women
### AI for Humanity — Phase 1 MVP + Agent API

An offline, low-cost AI vision assistant that detects objects through a
webcam and announces them by priority through spoken audio, built to help
blind and visually impaired women navigate their surroundings more safely
and independently.

This assistant also exposes an **Agent API** so the same detection logic
can be called from automation tools like **n8n**.

---

## What's included

| File | Purpose |
|---|---|
| `main.py` | The live assistant: webcam → YOLO detection → priority classification → beep + spoken audio alerts |
| `api_server.py` | HTTP API exposing the same detection logic, for use with n8n or other tools |
| `list_voices.py` | Lists the text-to-speech voices installed on your PC |
| `test_speech.py` | Standalone script to test if text-to-speech works at all on your machine |
| `requirements.txt` | Python package dependencies |
| `.gitignore` | Keeps `venv/` and cache files out of git |

---

## Features (Phase 1 + enhancements)

- **Real-time object detection** using Ultralytics YOLO11n (runs on CPU, no GPU needed)
- **Priority classification** — HIGH (danger), MEDIUM (awareness), LOW (informational) — with color-coded bounding boxes
- **Spoken audio alerts** in natural phrasing (e.g. *"Car coming ahead, very close!"*, *"Person nearby, on your left."*)
- **Instant beep** for HIGH priority objects that get dangerously close, so you're warned immediately, not just once the sentence finishes speaking
- **Rough distance estimate** (very close / close / far) based on how large the object appears in frame
- **Left / center / right position** for every detection
- **Agent API** (`api_server.py`) so the same detection logic can run in automations like n8n
- **Configurable voice, speech rate, and volume** via command-line flags

---

## Setup

### 1. Install Python
Python 3.10+ is required. If you're on Python 3.14 or newer, this project has been tested and works, but if you hit install errors, fall back to Python 3.11–3.12.

### 2. Open the project folder
In VS Code: **File → Open Folder** → select this folder (the one containing `main.py`).

### 3. Create and activate a virtual environment
In the VS Code terminal:
```
python -m venv venv
venv\Scripts\activate
```
Your terminal prompt should now start with `(venv)`.

### 4. Install dependencies
```
pip install -r requirements.txt
```
This installs Ultralytics YOLO, OpenCV, pyttsx3, EasyOCR, and Flask. It can take a few minutes — this is normal.

---

## Running the assistant (webcam + audio)

```
python main.py
```

### Useful flags

| Flag | What it does | Example |
|---|---|---|
| `--camera` | Pick a specific webcam if you have more than one | `--camera 1` |
| `--conf` | Detection confidence threshold (0–1) | `--conf 0.6` |
| `--rate` | Speech speed in words per minute (lower = slower) | `--rate 140` |
| `--volume` | Speech volume, 0.0–1.0 | `--volume 1.0` |
| `--voice` | Use a specific installed voice (see `list_voices.py`) | `--voice "HKEY_LOCAL_MACHINE\...\TTS_MS_EN-US_ZIRA_11.0"` |
| `--no-window` | Run without the video display (audio-only) | `--no-window` |

Press **`q`** in the video window (or **Ctrl+C** in the terminal) to stop.

### Finding a clearer voice
```
python list_voices.py
```
This prints every installed voice with its exact ID, ready to paste into `--voice`.

---

## Troubleshooting speech (Windows)

Text-to-speech on Windows can be finicky. Here's what we found and fixed along the way, in case you hit these again after changes:

| Symptom | Cause | Fix already applied |
|---|---|---|
| Speech works once, then goes silent | pyttsx3's SAPI5 driver misbehaves when reused repeatedly in one process, especially alongside OpenCV's camera thread | Speech now runs in its own separate, persistent background process (see `SpeechWorker` in `main.py`) |
| Beep plays, but no voice at all | The speech process was buffering input instead of processing it immediately | The process is launched with Python's `-u` (unbuffered) flag |
| Speech noticeably delayed | Starting a brand-new Python process for every single sentence | Now only **one** speech process starts (at launch) and stays alive, so each sentence is instant after that |

If speech ever breaks again, run `python test_speech.py` first — if that alone doesn't produce sound, the problem is with pyttsx3/your system audio, not this project's code.

---

## Agent API (for n8n / automation)

`api_server.py` exposes the same detection + priority logic over HTTP, so you can send it a single image and get back structured JSON — no webcam or audio needed on that side.

### Run it locally
```
python api_server.py
```
By default it listens on `http://localhost:5000`.

### Endpoints

**`GET /health`** — no auth needed, quick check the server is alive
```
{"status": "ok"}
```

**`POST /detect`** — requires header `X-API-Key: <your key>`
- Body: `multipart/form-data` with a field named `image` (the photo file)
- Optional form field `conf` to set detection confidence (default 0.5)

Example with curl:
```
curl -X POST http://localhost:5000/detect -H "X-API-Key: changeme123" -F "image=@photo.jpg"
```

Example response:
```json
{
  "count": 2,
  "detections": [
    {
      "class": "car",
      "confidence": 0.87,
      "priority": "HIGH",
      "position": "ahead",
      "distance": "very close",
      "alert_text": "Car coming ahead, very close!",
      "box": [120.5, 80.2, 400.1, 300.7]
    },
    {
      "class": "person",
      "confidence": 0.91,
      "priority": "MEDIUM",
      "position": "on your left",
      "distance": "close",
      "alert_text": "Person nearby, on your left.",
      "box": [10.0, 50.0, 90.0, 280.0]
    }
  ]
}
```

### Setting your own API key
Set the `API_KEY` environment variable before running (falls back to `changeme123` for local testing only):
```
$env:API_KEY="yourSecretKey"
python api_server.py
```

---

## Deploying the API to the cloud (Render)

Running the API only on your laptop means it's only reachable while your laptop is on. To get a permanent public URL:

1. Push this project to a GitHub repository
2. Create a free account at **render.com**, sign in with GitHub
3. **New → Web Service**, select your repo/branch
4. Build command: `pip install -r requirements.txt`
5. Start command: `python api_server.py`
6. Add an environment variable: `API_KEY` = your own secret value
7. Deploy — first build takes several minutes (installing PyTorch/Ultralytics)

Once live, your API is reachable at `https://your-app-name.onrender.com/detect` — no laptop or tunnel required.

**Free tier note:** Render's free instances sleep after ~15 minutes of inactivity; the first request after sleeping can take 30–60 seconds to wake up.

---

## Using it in n8n

Add an **HTTP Request** node with:

| Setting | Value |
|---|---|
| Method | `POST` |
| URL | `https://your-app-name.onrender.com/detect` |
| Body Content Type | Form-Data (Multipart) |
| Body field | `image` → Binary Data (from a previous node) |
| Authentication | Header Auth → Header name `X-API-Key`, value = your secret key |

Test with **Execute Node** using a sample image — you should get back the same JSON shown above.

---

## Known limitations

- **Stock YOLO only knows COCO's 80 classes.** Hazards named in the original brief — open drains, staircases, fire, ramps, white canes, signboards — are **not** detectable yet. This is intentional groundwork for **Phase 3: custom model training**.
- **Distance is an estimate, not a measurement.** It's based on how large an object appears in the frame, not true camera calibration. Good enough for near/far awareness, not precise navigation.
- **English only**, using Windows' built-in SAPI5 voices.

---

## Roadmap (from the original project plan)

**Phase 2 — Enhanced Accessibility**
- More accurate distance estimation (camera calibration)
- Text reading via EasyOCR (signboards, labels, room numbers) — dependency already included, not yet wired into `main.py`
- Directional navigation guidance

**Phase 3 — Custom AI Training**
- Collect and label real-world images of open drains, stairs, ramps, white canes, and accessible pathways
- Fine-tune YOLO11n on this custom dataset
- Swap the new model into `main.py` / `api_server.py` — only `PRIORITY_MAP` and the `--model` flag need to change; the rest of the code already supports this

---

## Social Impact

This project aims to improve mobility, safety, confidence, and independence
for blind and visually impaired women, using accessible, low-cost, and
largely offline AI — in line with the "AI for Humanity" theme of building
inclusive technology for real-world accessibility challenges.