"""
AI for Humanity - Smart Vision Assistant for Blind Women
Phase 1 MVP

Pipeline:
    Webcam -> YOLO object detection -> Priority classification -> Audio alerts

Run:
    python main.py
    python main.py --camera 0 --conf 0.45 --no-window

Notes on priority mapping:
    Stock YOLO (Ultralytics YOLO11n) is trained on the 80-class COCO dataset.
    Several hazards named in the project doc (open drains, staircases, fire,
    road hazards, signboards) are NOT in COCO and will not be detected until
    Phase 3 (custom-trained model). This script is built so that adding those
    classes later is a one-line change to PRIORITY_MAP + swapping the model
    weights -- no other code needs to change.
"""

import argparse
import queue
import subprocess
import sys
import threading
import time
from collections import defaultdict

import cv2
import pyttsx3
from ultralytics import YOLO

try:
    import winsound  # Windows-only, built into Python, no install needed
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False


# ---------------------------------------------------------------------------
# Priority configuration
# ---------------------------------------------------------------------------
# Map COCO class names -> priority level.
# Classes not listed here default to "LOW".
# When you train the Phase 3 custom model, just add the new class names here
# under "HIGH" (e.g. "staircase", "open_drain", "fire", "white_cane").
PRIORITY_MAP = {
    # ---- HIGH (danger / immediate attention) ----
    "car": "HIGH",
    "bus": "HIGH",
    "truck": "HIGH",
    "motorcycle": "HIGH",
    "train": "HIGH",
    "fire hydrant": "HIGH",   # closest COCO proxy available for hazard markers
    "stop sign": "HIGH",

    # ---- MEDIUM (requires awareness) ----
    "person": "MEDIUM",
    "bicycle": "MEDIUM",
    "traffic light": "MEDIUM",
    "chair": "MEDIUM",
    "bench": "MEDIUM",
    "dining table": "MEDIUM",
    "couch": "MEDIUM",

    # ---- LOW (informational) ----
    "potted plant": "LOW",    # tree/plant proxy
    "book": "LOW",
    "tv": "LOW",
    "laptop": "LOW",
    "clock": "LOW",
    "vase": "LOW",
    "backpack": "LOW",
    "umbrella": "LOW",
    "handbag": "LOW",
    "suitcase": "LOW",
    "bottle": "LOW",
    "cup": "LOW",
    "cell phone": "LOW",
    "refrigerator": "LOW",
    "microwave": "LOW",
    "oven": "LOW",
    "sink": "LOW",
    "bed": "LOW",
    "toilet": "LOW",
}

# Re-announce the same (class, position) combo only after this many seconds,
# so the assistant doesn't repeat itself every single frame.
COOLDOWN_SECONDS = {
    "HIGH": 3.0,
    "MEDIUM": 6.0,
    "LOW": 12.0,
}

# Bounding box colors per priority (BGR for OpenCV)
BOX_COLORS = {
    "HIGH": (0, 0, 255),      # red
    "MEDIUM": (0, 165, 255),  # orange
    "LOW": (0, 200, 0),       # green
}

# Distance is estimated from how much of the frame height the object's
# bounding box takes up. This is a rough proxy, not a true measurement --
# a real "meters" estimate needs camera calibration (a good Phase 2
# upgrade later). These thresholds work reasonably well out of the box.
DISTANCE_THRESHOLDS = {
    "very close": 0.5,   # box takes up 50%+ of the frame height
    "close": 0.25,       # box takes up 25-50% of the frame height
    # anything smaller is treated as "far" and not called out
}

# Play an instant beep (separate from speech) whenever a HIGH priority
# object gets this close, so the user gets warned immediately instead of
# waiting for the spoken sentence to queue and play.
BEEP_TRIGGER_DISTANCE = "very close"
BEEP_COOLDOWN_SECONDS = 1.5
BEEP_FREQUENCY_HZ = 1000
BEEP_DURATION_MS = 150


def get_priority(class_name: str) -> str:
    return PRIORITY_MAP.get(class_name, "LOW")


def get_position(box_center_x: float, frame_width: int) -> str:
    """Rough left / center / right estimate based on where the box sits."""
    third = frame_width / 3
    if box_center_x < third:
        return "on your left"
    elif box_center_x > 2 * third:
        return "on your right"
    return "ahead"


def estimate_distance_bucket(box_height: float, frame_height: int) -> str:
    """Rough near/mid/far estimate based on how tall the box is relative
    to the frame. Not a real measurement -- see DISTANCE_THRESHOLDS comment."""
    ratio = box_height / frame_height
    if ratio >= DISTANCE_THRESHOLDS["very close"]:
        return "very close"
    elif ratio >= DISTANCE_THRESHOLDS["close"]:
        return "close"
    return "far"


def play_beep_async():
    """Fires a short beep on its own thread so it never blocks the main
    detection loop. Windows-only (uses the built-in winsound module)."""
    if not HAS_WINSOUND:
        return
    threading.Thread(
        target=lambda: winsound.Beep(BEEP_FREQUENCY_HZ, BEEP_DURATION_MS),
        daemon=True,
    ).start()


def build_alert_text(class_name: str, priority: str, position: str, distance: str) -> str:
    label = class_name.replace("_", " ")

    if priority == "HIGH":
        # e.g. "Car coming ahead, very close!"
        if distance == "very close":
            return f"{label.capitalize()} coming {position}, very close!"
        elif distance == "close":
            return f"{label.capitalize()} coming {position}!"
        return f"{label.capitalize()} coming {position}."
    elif priority == "MEDIUM":
        if distance in ("very close", "close"):
            return f"{label.capitalize()} nearby, {position}."
        return f"{label.capitalize()} detected {position}."
    else:
        return f"{label.capitalize()} detected {position}."


# ---------------------------------------------------------------------------
# Text-to-speech worker
# ---------------------------------------------------------------------------
# Each sentence is spoken in its own separate Python process rather than a
# background thread. This sounds heavier than it is: on Windows, pyttsx3's
# speech engine (SAPI5) uses COM, and COM can silently stop producing audio
# when OpenCV's camera capture and a long-lived speech thread share the
# same process. Running each utterance as its own short-lived subprocess
# fully isolates it from OpenCV, which reliably fixes this class of bug.
_SPEAK_SCRIPT = (
    "import sys, pyttsx3\n"
    "rate = int(sys.argv[1])\n"
    "volume = float(sys.argv[2])\n"
    "voice_id = sys.argv[3]\n"
    "text = sys.argv[4]\n"
    "engine = pyttsx3.init()\n"
    "engine.setProperty('rate', rate)\n"
    "engine.setProperty('volume', volume)\n"
    "if voice_id:\n"
    "    engine.setProperty('voice', voice_id)\n"
    "engine.say(text)\n"
    "engine.runAndWait()\n"
)


class SpeechWorker:
    def __init__(self, rate: int = 145, volume: float = 1.0, voice_id: str = None):
        self._rate = rate
        self._volume = volume
        self._voice_id = voice_id or ""
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._stop_flag = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW  # don't flash a console window each time
        while not self._stop_flag.is_set():
            try:
                text = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            cmd = [
                sys.executable, "-c", _SPEAK_SCRIPT,
                str(self._rate), str(self._volume), self._voice_id, text,
            ]
            try:
                subprocess.run(cmd, timeout=10, creationflags=creationflags)
            except Exception as e:
                print(f"TTS error: {e}")

    def say(self, text: str):
        # Drop the request if the queue is backing up, so alerts stay
        # near-real-time instead of lagging behind what's on screen.
        if self._queue.qsize() < 3:
            self._queue.put(text)

    def stop(self):
        self._stop_flag.set()
        self._thread.join(timeout=2.0)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Smart Vision Assistant - Phase 1 MVP")
    parser.add_argument("--camera", type=int, default=0, help="Webcam index (default 0)")
    parser.add_argument("--model", type=str, default="yolo11n.pt", help="YOLO model weights")
    parser.add_argument("--conf", type=float, default=0.5, help="Detection confidence threshold")
    parser.add_argument("--no-window", action="store_true",
                         help="Run without a display window (audio-only mode)")
    parser.add_argument("--rate", type=int, default=145,
                         help="Speech rate in words per minute (default 145, lower = slower)")
    parser.add_argument("--volume", type=float, default=1.0,
                         help="Speech volume from 0.0 to 1.0 (default 1.0)")
    parser.add_argument("--voice", type=str, default=None,
                         help="Voice ID to use (run list_voices.py to see options on your PC)")
    args = parser.parse_args()

    print("Loading YOLO model...")
    model = YOLO(args.model)

    print(f"Opening camera index {args.camera}...")
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print("ERROR: Could not open webcam. Try a different --camera index.")
        return

    speaker = SpeechWorker(rate=args.rate, volume=args.volume, voice_id=args.voice)
    speaker.say("Smart vision assistant started.")

    last_spoken = defaultdict(float)  # key: (class_name, position, distance) -> timestamp
    last_beep = defaultdict(float)    # key: (class_name, position) -> timestamp

    print("Running. Press 'q' in the video window to quit (or Ctrl+C in terminal).")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("WARNING: Failed to read frame from webcam.")
                break

            frame_height, frame_width = frame.shape[:2]
            results = model.predict(frame, conf=args.conf, verbose=False)[0]

            # Sort detections so HIGH priority alerts are spoken first if
            # several things are detected in the same frame.
            detections = []
            for box in results.boxes:
                cls_id = int(box.cls[0])
                class_name = model.names[cls_id]
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                center_x = (x1 + x2) / 2
                box_height = y2 - y1
                priority = get_priority(class_name)
                position = get_position(center_x, frame_width)
                distance = estimate_distance_bucket(box_height, frame_height)
                detections.append((priority, class_name, position, distance, confidence, (x1, y1, x2, y2)))

            priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            detections.sort(key=lambda d: priority_order[d[0]])

            now = time.time()
            for priority, class_name, position, distance, confidence, (x1, y1, x2, y2) in detections:
                # Draw box + label if we're showing a window
                if not args.no_window:
                    color = BOX_COLORS[priority]
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                    label = f"{class_name} {confidence:.2f} [{priority}] {distance}"
                    cv2.putText(frame, label, (int(x1), max(int(y1) - 8, 0)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                # Instant beep for anything HIGH priority that's gotten very
                # close -- fires immediately, doesn't wait on the speech queue.
                if priority == "HIGH" and distance == BEEP_TRIGGER_DISTANCE:
                    beep_key = (class_name, position)
                    if now - last_beep[beep_key] >= BEEP_COOLDOWN_SECONDS:
                        play_beep_async()
                        last_beep[beep_key] = now

                # Cooldown check before speaking
                key = (class_name, position, distance)
                cooldown = COOLDOWN_SECONDS[priority]
                if now - last_spoken[key] >= cooldown:
                    alert_text = build_alert_text(class_name, priority, position, distance)
                    speaker.say(alert_text)
                    last_spoken[key] = now
                    print(f"[{priority}] {alert_text}")

            if not args.no_window:
                cv2.imshow("Smart Vision Assistant - Phase 1", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    except KeyboardInterrupt:
        pass
    finally:
        speaker.say("Smart vision assistant shutting down.")
        time.sleep(1.5)  # let the final message finish speaking
        speaker.stop()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
