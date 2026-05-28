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
echo "  - yolo-card-nano.onnx — card detection."
echo "    REALITY CHECK (2026-05-28): the current best.pt is a YOLOv8m (~26M params)."
echo "    Exporting it yields ~51MB FP16 / ~103MB FP32 ONNX — NOT a 6MB nano. The"
echo "    file currently shipped to web-app/public/models/yolo-card-nano.onnx IS the"
echo "    51MB YOLOv8m (misnamed 'nano') and is slow to load + infer in-browser."
echo "    A true ~6MB browser model requires a RETRAINED YOLOv8n .pt — a re-export"
echo "    of best.pt CANNOT shrink the architecture. Deliver the retrained nano .onnx"
echo "    separately (model binaries are gitignored here)."
echo ""
echo "Download sources:"
echo "  MobileFaceNet: https://github.com/deepinsight/insightface (export required)"
echo "  Card (current YOLOv8m): export with"
echo "    python -c \"from ultralytics import YOLO; YOLO('best.pt').export(format='onnx', imgsz=640, half=True, simplify=True)\""
echo "    (half=True → ~51MB FP16; half=False → ~103MB FP32). For the ~6MB browser"
echo "    target, use Ayşenur's retrained YOLOv8n .pt, then export the same way."
