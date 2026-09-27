"""
Smart Vision Assistant - Agent API

A small local HTTP server that exposes the same YOLO detection + priority
classification logic as main.py, but over HTTP instead of a live webcam --
so tools like n8n can send it a photo and get back structured detection
data (no audio; that's still handled by main.py on the laptop itself).

Run:
    python api_server.py

Then POST an image to:
    http://localhost:5000/detect

See README.md for exact n8n HTTP Request node settings.
"""

import os

from flask import Flask, request, jsonify
import cv2
import numpy as np
from ultralytics import YOLO

from main import get_priority, get_position, estimate_distance_bucket, build_alert_text

app = Flask(__name__)

print("Loading YOLO model...")
model = YOLO("yolo11n.pt")

API_KEY = os.environ.get("API_KEY", "changeme123")

PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


@app.before_request
def check_auth():
    if request.path == "/health":
        return None
    provided_key = request.headers.get("X-API-Key")
    if provided_key != API_KEY:
        return jsonify({"error": "Unauthorized. Include header X-API-Key with the correct key."}), 401


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/detect", methods=["POST"])
def detect():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided. Send it as form-data field named 'image'."}), 400

    file = request.files["image"]
    file_bytes = np.frombuffer(file.read(), np.uint8)
    frame = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify({"error": "Could not decode the uploaded image."}), 400

    frame_height, frame_width = frame.shape[:2]
    conf = float(request.form.get("conf", 0.5))
    results = model.predict(frame, conf=conf, verbose=False)[0]

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
        alert_text = build_alert_text(class_name, priority, position, distance)

        detections.append({
            "class": class_name,
            "confidence": round(confidence, 3),
            "priority": priority,
            "position": position,
            "distance": distance,
            "alert_text": alert_text,
            "box": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
        })

    detections.sort(key=lambda d: PRIORITY_ORDER[d["priority"]])

    return jsonify({
        "count": len(detections),
        "detections": detections,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Agent API running. POST images to http://localhost:{port}/detect")
    app.run(host="0.0.0.0", port=port)
