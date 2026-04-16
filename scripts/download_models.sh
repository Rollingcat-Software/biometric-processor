#!/bin/bash
# Download ONNX models for client-side biometric engine
# Run from biometric-processor directory

set -e
MODELS_DIR="./app/core/card_type_model"
mkdir -p "$MODELS_DIR"

echo "Models already present:"
ls -lh "$MODELS_DIR"

echo ""
echo "NOTE: For client-side web models, place the following in web-app/public/models/:"
echo "  - mobilefacenet.onnx (~4.9 MB) — face embedding (MobileFaceNet INT8)"
echo "  - yolo-card-nano.onnx (~6.2 MB) — card detection (YOLOv8n FP16)"
echo ""
echo "Download sources:"
echo "  MobileFaceNet: https://github.com/deepinsight/insightface (export required)"
echo "  YOLOv8n card: re-export from best.pt with: yolo export model=best.pt format=onnx imgsz=640"
echo ""
echo "To export YOLOv8n nano from existing best.pt:"
echo "  cd app/core/card_type_model"
echo "  python -c \"from ultralytics import YOLO; m=YOLO('best.pt'); m.export(format='onnx', imgsz=640, half=False, simplify=True)\""
