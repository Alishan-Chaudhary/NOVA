from fastapi import FastAPI, UploadFile, File
from ultralytics import YOLO
import cv2
import numpy as np
from datetime import datetime

app = FastAPI(
    title="Netra AI Vision API",
    description="Real-time context and movement analyzer"
)

# Load YOLO model
model = YOLO("yolo26n.pt")

# Store previous object positions
previous_positions = {}


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Netra AI Vision Engine",
        "version": "1.0"
    }


@app.post("/analyze")
async def analyze(image: UploadFile = File(...)):

    # Read uploaded image
    contents = await image.read()

    image_array = np.frombuffer(
        contents,
        np.uint8
    )

    frame = cv2.imdecode(
        image_array,
        cv2.IMREAD_COLOR
    )

    if frame is None:
        return {
            "error": "Could not read image"
        }

    # YOLO tracking
    results = model.track(
        frame,
        persist=True,
        tracker="bytetrack.yaml",
        conf=0.4,
        verbose=False
    )

    result = results[0]

    objects = []

    frame_width = frame.shape[1]
    frame_height = frame.shape[0]

    if result.boxes:

        for box in result.boxes:

            # Object class
            class_id = int(box.cls[0])

            object_type = model.names[class_id]

            # Confidence
            confidence = float(box.conf[0])

            # Bounding box
            x1, y1, x2, y2 = (
                box.xyxy[0].tolist()
            )

            # Center
            center_x = int((x1 + x2) / 2)
            center_y = int((y1 + y2) / 2)

            # Tracking ID
            if box.id is not None:
                track_id = int(box.id[0])
            else:
                track_id = None

            # -------------------------
            # POSITION
            # -------------------------

            if center_x < frame_width / 3:
                position = "left"

            elif center_x < (frame_width * 2 / 3):
                position = "center"

            else:
                position = "right"

            # -------------------------
            # MOVEMENT
            # -------------------------

            movement = "unknown"

            if track_id is not None:

                if track_id in previous_positions:

                    previous_x = previous_positions[track_id]["x"]
                    previous_y = previous_positions[track_id]["y"]

                    dx = center_x - previous_x
                    dy = center_y - previous_y

                    movement_threshold = 5

                    if abs(dx) > movement_threshold:

                        if dx > 0:
                            movement = "moving_right"
                        else:
                            movement = "moving_left"

                    elif abs(dy) > movement_threshold:

                        if dy > 0:
                            movement = "moving_down"
                        else:
                            movement = "moving_up"

                    else:
                        movement = "stationary"

                previous_positions[track_id] = {
                    "x": center_x,
                    "y": center_y
                }

            # -------------------------
            # OBJECT DATA
            # -------------------------

            objects.append({

                "id": track_id,

                "type": object_type,

                "confidence": round(
                    confidence,
                    2
                ),

                "position": position,

                "movement": movement,

                "center": {
                    "x": center_x,
                    "y": center_y
                },

                "bounding_box": {
                    "x1": int(x1),
                    "y1": int(y1),
                    "x2": int(x2),
                    "y2": int(y2)
                }

            })

    # -------------------------
    # CONTEXT
    # -------------------------

    risk = "low"

    messages = []

    for obj in objects:

        object_type = obj["type"]

        movement = obj["movement"]

        position = obj["position"]

        # Vehicle approaching
        if object_type in [
            "car",
            "motorcycle",
            "bus",
            "truck"
        ]:

            if movement in [
                "moving_left",
                "moving_right",
                "moving_up",
                "moving_down"
            ]:

                risk = "medium"

                messages.append(
                    f"{object_type} moving from {position}"
                )

        # Person
        if object_type == "person":

            if movement != "stationary":

                messages.append(
                    f"Person moving on the {position}"
                )

    # -------------------------
    # FINAL RESPONSE
    # -------------------------

    response = {

        "timestamp":
            datetime.now().isoformat(),

        "scene": {

            "width": frame_width,

            "height": frame_height,

            "object_count":
                len(objects)

        },

        "objects": objects,

        "context": {

            "risk": risk,

            "messages": messages

        }

    }

    return response