# Smart Vision Assistant — Phase 1 MVP

AI for Humanity: an offline, low-cost vision assistant that detects objects
through a webcam and announces them by priority, using spoken audio alerts.

## What's included in this MVP

- Real-time webcam capture (OpenCV)
- Object detection (Ultralytics YOLO11n)
- Priority classification (HIGH / MEDIUM / LOW) with color-coded bounding boxes
- Spoken audio alerts (pyttsx3, fully offline, no cloud API)
- Left / center / right position estimate for each detected object
- Cooldown logic so the assistant doesn't repeat the same alert every frame

## Setup (Windows)

1. Install Python 3.10+ from python.org (check "Add to PATH" during install).
2. Open a terminal in this folder and create a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
   The first run of the script will also auto-download the `yolo11n.pt`
   weights (~5-6 MB) from Ultralytics — this requires internet once, then
   the model runs fully offline afterward.

## Run it

```
python main.py
```

Optional flags:
```
python main.py --camera 0          # pick a specific webcam
python main.py --conf 0.6          # raise/lower detection confidence
python main.py --no-window         # audio-only, no video display (for a headless/embedded setup)
```

Press `q` in the video window to quit, or Ctrl+C in the terminal.

## Known limitation in this MVP (by design)

Stock YOLO11n is trained on the 80-class COCO dataset. Several hazards from
the project brief — **open drains, staircases, fire, road hazards,
signboards, ramps, white canes** — are *not* COCO classes, so they won't be
detected yet. This is exactly what Phase 3 (custom model training) in the
project plan is for.

The code is structured so this is easy to extend later:
- `PRIORITY_MAP` in `main.py` is the single place that maps a class name to
  HIGH/MEDIUM/LOW — add your new custom class names there.
- Swap `--model yolo11n.pt` for your custom-trained weights file once
  Phase 3 training is done. No other code changes needed.

## Suggested next steps (Phase 2)

- **Distance estimation**: use bounding-box height/area as a rough proxy for
  distance, or add a monocular depth model (e.g. MiDaS) for better accuracy.
- **Text reading**: EasyOCR is already in `requirements.txt`; wire it in to
  read signboards/labels on demand (e.g. triggered by a keypress or voice
  command, since running OCR every frame is expensive).
- **Navigation guidance**: combine position + distance to give directional
  instructions ("move slightly left to avoid the chair").

## Hardware notes

YOLO11n is the smallest/fastest Ultralytics model and runs in real time on a
CPU-only laptop, which matches the "low-cost, offline" goal. If you later
move to a Raspberry Pi or similar embedded device, consider exporting the
model to ONNX or NCNN format for a further speed boost.
