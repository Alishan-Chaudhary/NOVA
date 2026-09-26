import cv2
import requests
import json
import time

API_URL = "http://127.0.0.1:8000/analyze"

print("Starting Netra camera client...")
print("Connecting to:", API_URL)

# Open webcam
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("ERROR: Could not open camera.")
    input("Press Enter to exit...")
    exit()

print("Camera connected successfully.")
print("Press Q to quit.")

frame_count = 0

while True:

    success, frame = cap.read()

    if not success:
        print("ERROR: Could not read camera frame.")
        break

    frame_count += 1

    # Send only every 5th frame
    # This prevents overwhelming the API
    if frame_count % 5 == 0:

        try:

            # Convert frame to JPEG
            success_encode, buffer = cv2.imencode(
                ".jpg",
                frame
            )

            if not success_encode:
                print("Could not encode frame.")
                continue

            # Prepare multipart upload
            files = {
                "image": (
                    "camera.jpg",
                    buffer.tobytes(),
                    "image/jpeg"
                )
            }

            # Send to FastAPI
            response = requests.post(
                API_URL,
                files=files,
                timeout=10
            )

            print("\n==============================")
            print("NETRA API RESPONSE")
            print("==============================")

            print("Status:", response.status_code)

            if response.ok:

                data = response.json()

                print(
                    json.dumps(
                        data,
                        indent=2
                    )
                )

            else:

                print(
                    "API ERROR:",
                    response.text
                )

        except requests.exceptions.ConnectionError:

            print(
                "ERROR: Cannot connect to FastAPI."
            )

        except requests.exceptions.Timeout:

            print(
                "ERROR: API request timed out."
            )

        except Exception as e:

            print(
                "ERROR:",
                e
            )

    # Show camera
    cv2.imshow(
        "Netra AI Camera",
        frame
    )

    # Press Q to quit
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()

cv2.destroyAllWindows()

print("Netra camera client stopped.")