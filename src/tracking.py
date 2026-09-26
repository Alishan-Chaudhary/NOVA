from ultralytics import YOLO

model = YOLO("yolo26n.pt")

results = model.track(
    source=0,
    show=True,
    tracker="bytetrack.yaml"
)