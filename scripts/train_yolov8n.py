#!/usr/bin/env python3
"""
YOLOv8n Card Detection Training Script
========================================

Trains a YOLOv8n (nano, 3.2M params) model to replace the current
YOLOv8m (25.8M params) model for browser-side real-time card detection.

Expected result: ~6MB ONNX model with ~100ms inference in ONNX Runtime Web (WASM).

Original YOLOv8m training parameters (extracted from best.pt metadata):
  - Base model: yolov8m.pt
  - Dataset: card_dataset_final/data.yaml
  - Epochs: 120, Batch: 8, Image size: 768
  - Cosine LR, lr0=0.003, patience=25
  - 5 classes: ehliyet, pasaport, ogrenci_karti, tc_kimlik, akademisyen_karti

Usage:
  1. Place your dataset at ./card_dataset_final/ (or update DATASET_PATH)
  2. Run: python train_yolov8n.py
  3. Output: runs/detect/card_nano/weights/best.pt + best.onnx

Requirements:
  pip install ultralytics>=8.0.0 torch torchvision onnx onnxruntime

Dataset structure expected (same as original training):
  card_dataset_final/
    data.yaml
    train/
      images/
      labels/
    val/
      images/
      labels/
    test/  (optional)
      images/
      labels/

data.yaml should contain:
  train: train/images
  val: val/images
  test: test/images  # optional
  nc: 5
  names: ['ehliyet', 'pasaport', 'ogrenci_karti', 'tc_kimlik', 'akademisyen_karti']
"""

import argparse
import sys
from pathlib import Path


def create_sample_data_yaml(output_path: Path):
    """Create a sample data.yaml for reference."""
    content = """# FIVUCSAS Card Detection Dataset
# Place this file at the root of your dataset directory

train: train/images
val: val/images
test: test/images

nc: 5
names:
  0: ehliyet
  1: pasaport
  2: ogrenci_karti
  3: tc_kimlik
  4: akademisyen_karti
"""
    output_path.write_text(content)
    print(f"Sample data.yaml written to {output_path}")


def train(
    dataset_path: str = "card_dataset_final/data.yaml",
    epochs: int = 100,
    batch: int = 16,
    imgsz: int = 640,
    device: str = "0",
    project: str = "runs/detect",
    name: str = "card_nano",
    resume: bool = False,
):
    """Train YOLOv8n on the card detection dataset."""
    from ultralytics import YOLO

    # Use nano pretrained model as base
    if resume and Path(f"{project}/{name}/weights/last.pt").exists():
        print("Resuming from last checkpoint...")
        model = YOLO(f"{project}/{name}/weights/last.pt")
    else:
        print("Starting fresh training from yolov8n.pt (COCO pretrained)...")
        model = YOLO("yolov8n.pt")

    # Verify dataset exists
    data_path = Path(dataset_path)
    if not data_path.exists():
        print(f"\nERROR: Dataset not found at '{dataset_path}'")
        print("\nPlease provide the card_dataset_final directory with the following structure:")
        print("  card_dataset_final/")
        print("    data.yaml")
        print("    train/images/  (training images)")
        print("    train/labels/  (YOLO format .txt label files)")
        print("    val/images/    (validation images)")
        print("    val/labels/    (YOLO format .txt label files)")
        print("\nTo create a sample data.yaml, run:")
        print("  python train_yolov8n.py --create-sample-yaml")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"FIVUCSAS Card Detection - YOLOv8n Training")
    print(f"{'='*60}")
    print(f"Dataset: {dataset_path}")
    print(f"Epochs: {epochs}")
    print(f"Batch size: {batch}")
    print(f"Image size: {imgsz}")
    print(f"Device: {device}")
    print(f"{'='*60}\n")

    # Train with optimized hyperparameters for nano model
    # Key differences from original medium training:
    # - Smaller image size (640 vs 768) for faster inference
    # - Larger batch (16 vs 8) since nano uses less memory
    # - Slightly higher lr0 for nano convergence
    # - More aggressive augmentation to compensate for smaller model capacity
    results = model.train(
        data=dataset_path,
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device=device,
        project=project,
        name=name,
        exist_ok=True,
        # Learning rate
        lr0=0.005,           # Slightly higher than medium (0.003) for nano
        lrf=0.01,            # Same final LR factor
        cos_lr=True,         # Cosine annealing (same as original)
        warmup_epochs=5.0,   # Longer warmup for nano
        # Regularization
        weight_decay=0.0005,
        dropout=0.0,
        # Augmentation (more aggressive for smaller model)
        mosaic=0.9,          # Increased from 0.8
        mixup=0.1,           # Increased from 0.05
        scale=0.5,
        translate=0.1,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        erasing=0.4,
        # Training config
        patience=30,         # Slightly more patience than original (25)
        save=True,
        save_period=10,
        plots=True,
        verbose=True,
        amp=True,
        workers=4,
        # Loss weights (same as original)
        box=7.5,
        cls=0.5,
        dfl=1.5,
        close_mosaic=10,
    )

    print(f"\nTraining complete! Results saved to {project}/{name}/")
    return model, results


def export_onnx(
    model_path: str = "runs/detect/card_nano/weights/best.pt",
    imgsz: int = 640,
):
    """Export trained model to ONNX format optimized for browser inference."""
    from ultralytics import YOLO

    pt_path = Path(model_path)
    if not pt_path.exists():
        print(f"ERROR: Model not found at '{model_path}'")
        sys.exit(1)

    model = YOLO(model_path)

    print(f"\n{'='*60}")
    print(f"Exporting to ONNX (browser-optimized)")
    print(f"{'='*60}")
    print(f"Input: {model_path}")
    print(f"Image size: {imgsz}")
    print(f"{'='*60}\n")

    # Export to ONNX with settings optimized for ONNX Runtime Web
    onnx_path = model.export(
        format="onnx",
        imgsz=imgsz,
        simplify=True,     # ONNX simplifier for smaller graph
        opset=13,          # Compatible with ONNX Runtime Web 1.14+
        half=False,        # FP32 for WASM compatibility (WASM doesn't support FP16)
        dynamic=False,     # Static shapes for WASM performance
        batch=1,           # Single image inference
    )

    # Also export FP16 for WebGPU (when available)
    onnx_fp16_path = model.export(
        format="onnx",
        imgsz=imgsz,
        simplify=True,
        opset=13,
        half=True,         # FP16 for WebGPU backend
        dynamic=False,
        batch=1,
    )

    import os
    onnx_size = os.path.getsize(onnx_path) / (1024 * 1024)
    fp16_size = os.path.getsize(onnx_fp16_path) / (1024 * 1024)

    print(f"\nExported models:")
    print(f"  FP32 ONNX: {onnx_path} ({onnx_size:.1f} MB)")
    print(f"  FP16 ONNX: {onnx_fp16_path} ({fp16_size:.1f} MB)")
    print(f"\nExpected browser performance:")
    print(f"  WASM (FP32): ~80-150ms per frame")
    print(f"  WebGPU (FP16): ~30-60ms per frame (when supported)")

    return onnx_path


def validate(model_path: str = "runs/detect/card_nano/weights/best.pt"):
    """Run validation on the trained model."""
    from ultralytics import YOLO

    model = YOLO(model_path)
    metrics = model.val()

    print(f"\nValidation Results:")
    print(f"  mAP50: {metrics.box.map50:.4f}")
    print(f"  mAP50-95: {metrics.box.map:.4f}")
    print(f"  Precision: {metrics.box.mp:.4f}")
    print(f"  Recall: {metrics.box.mr:.4f}")

    return metrics


def compare_models(
    medium_path: str = "app/core/card_type_model/best.pt",
    nano_path: str = "runs/detect/card_nano/weights/best.pt",
):
    """Compare medium and nano model sizes and parameter counts."""
    from ultralytics import YOLO
    import os

    print(f"\n{'='*60}")
    print(f"Model Comparison")
    print(f"{'='*60}")

    for label, path in [("Medium (current)", medium_path), ("Nano (new)", nano_path)]:
        if not Path(path).exists():
            print(f"  {label}: NOT FOUND at {path}")
            continue
        model = YOLO(path)
        params = sum(p.numel() for p in model.model.parameters())
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"  {label}:")
        print(f"    Parameters: {params:,}")
        print(f"    File size: {size_mb:.1f} MB")
        print(f"    Classes: {model.names}")

    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="YOLOv8n Card Detection Training for FIVUCSAS"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Train command
    train_parser = subparsers.add_parser("train", help="Train YOLOv8n model")
    train_parser.add_argument(
        "--data", default="card_dataset_final/data.yaml",
        help="Path to data.yaml"
    )
    train_parser.add_argument("--epochs", type=int, default=100)
    train_parser.add_argument("--batch", type=int, default=16)
    train_parser.add_argument("--imgsz", type=int, default=640)
    train_parser.add_argument("--device", default="0", help="GPU device (0, cpu)")
    train_parser.add_argument("--resume", action="store_true")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export to ONNX")
    export_parser.add_argument(
        "--model", default="runs/detect/card_nano/weights/best.pt"
    )
    export_parser.add_argument("--imgsz", type=int, default=640)

    # Validate command
    val_parser = subparsers.add_parser("val", help="Validate trained model")
    val_parser.add_argument(
        "--model", default="runs/detect/card_nano/weights/best.pt"
    )

    # Compare command
    subparsers.add_parser("compare", help="Compare medium vs nano models")

    # Create sample data.yaml
    sample_parser = subparsers.add_parser(
        "create-sample-yaml", help="Create sample data.yaml"
    )
    sample_parser.add_argument("--output", default="card_dataset_final/data.yaml")

    # Full pipeline
    subparsers.add_parser("full", help="Train + export + validate")

    args = parser.parse_args()

    if args.command == "train":
        train(
            dataset_path=args.data,
            epochs=args.epochs,
            batch=args.batch,
            imgsz=args.imgsz,
            device=args.device,
            resume=args.resume,
        )
    elif args.command == "export":
        export_onnx(model_path=args.model, imgsz=args.imgsz)
    elif args.command == "val":
        validate(model_path=args.model)
    elif args.command == "compare":
        compare_models()
    elif args.command == "create-sample-yaml":
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        create_sample_data_yaml(output)
    elif args.command == "full":
        model, results = train()
        export_onnx()
        validate()
        compare_models()
    else:
        parser.print_help()
        print("\nQuick start:")
        print("  1. Place dataset at card_dataset_final/")
        print("  2. python train_yolov8n.py train --device 0")
        print("  3. python train_yolov8n.py export")
        print("  4. Upload best.onnx to Hostinger /auth-test/card_model_nano.onnx")


if __name__ == "__main__":
    main()
