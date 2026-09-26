import cv2

print("Starting camera test...")

cap = cv2.VideoCapture(0)

print("Camera object created:", cap.isOpened())

if not cap.isOpened():
    print("ERROR: Could not open camera.")
    print("Try camera index 1...")
    
    cap = cv2.VideoCapture(1)

    print("Camera 1 opened:", cap.isOpened())

if not cap.isOpened():
    print("ERROR: No camera could be opened.")
    input("Press Enter to exit...")
    exit()

print("Camera successfully opened!")

while True:

    ret, frame = cap.read()

    if not ret:
        print("ERROR: Could not read frame.")
        break

    cv2.imshow("Netra Camera Test", frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()

print("Camera closed.")