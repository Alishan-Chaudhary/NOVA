import cv2
from ultralytics import YOLO

model = YOLO("yolo26n.pt")

cap = cv2.VideoCapture(0)

previous_positions = {}

previous_heights = {}



while True:

    success, frame = cap.read()

    if not success:
        break

    results = model.track(
        frame,
        persist=True,
        tracker="bytetrack.yaml",
        conf=0.4
    )

    result = results[0]

    if result.boxes:

        boxes = result.boxes

        for box in boxes:

            class_id = int(box.cls[0])
            confidence = float(box.conf[0])

            object_name = model.names[class_id]

            if box.id is not None:
                track_id = int(box.id[0])

                print(
                    f"ID: {track_id} | "
                    f"Object: {object_name} | "
                    f"Confidence: {confidence:.2f}"
                )

    annotated_frame = result.plot()

    cv2.imshow(
        "Netra AI",
        annotated_frame
    )

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

    x1, y1, x2, y2 = box.xyxy[0].tolist()

    center_x = int((x1 + x2) / 2)
    center_y = int((y1 + y2) / 2)

    width = frame.shape[1]

    if center_x < width / 3:
        position = "left"

    elif center_x < 2 * width / 3:
        position = "center"

    else:
        position = "right"

    if track_id in previous_positions:

        previous_x, previous_y = previous_positions[track_id]

        dx = center_x - previous_x
        dy = center_y - previous_y

        if abs(dx) > 5:

            if dx > 0:
                movement = "moving_right"
            else:
                movement = "moving_left"

        else:

            movement = "stationary"

    else:

        movement = "unknown"

    previous_positions[track_id] = (
        center_x,
        center_y
    )

    height = y2 - y1

    if track_id in previous_heights:

        previous_height = previous_heights[track_id]

        change = height - previous_height

        if change > 8:
            movement_depth = "approaching"

        elif change < -8:
            movement_depth = "moving_away"

        else:
            movement_depth = "stable"

    else:

        movement_depth = "unknown"

    previous_heights[track_id] = height


cap.release()
cv2.destroyAllWindows()