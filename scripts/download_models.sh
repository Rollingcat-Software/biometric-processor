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
echo "  - yolo-card-nano.onnx (~12.3 MB) — card detection (true YOLOv8n, opset 12)."
echo "    As of 2026-05-29 the retrained YOLOv8n was delivered and integrated: the"
echo "    in-repo app/core/card_type_model/best.onnx (12.3 MB, true YOLOv8n, opset 12)"
echo "    is force-tracked and best.pt was removed (bio #116). Copy best.onnx to"
echo "    web-app/public/models/yolo-card-nano.onnx and record its SHA256 in the"
echo "    client manifest. (The earlier 51 MB YOLOv8m mislabeled 'nano' is gone.)"
echo ""
echo "Download sources:"
echo "  MobileFaceNet: https://github.com/deepinsight/insightface (export required)"
echo "  Card: app/core/card_type_model/best.onnx (true YOLOv8n, opset 12, ~12.3 MB)"
echo "    is already in-repo (bio #116); no re-export step is needed."
