#!/usr/bin/env python3
"""
Knowledge Distillation: YOLOv8m -> YOLOv8n
============================================

Uses the existing YOLOv8m (medium) card detection model as a "teacher"
to generate pseudo-labels on unlabeled card images, then trains YOLOv8n
(nano) on those pseudo-labels.

This approach does NOT require the original training dataset.
It only needs:
  1. The trained YOLOv8m model (best.pt) -- already on the server
  2. A collection of card images (can be scraped, photographed, or synthetic)

Workflow:
  1. Collect card images into raw_images/ directory
  2. Run teacher inference to generate pseudo-labels
  3. Train YOLOv8n student on pseudo-labeled data
  4. Export to ONNX for browser deployment

Usage:
  # Step 1: Generate pseudo-labels from teacher model
  python distill_yolov8n.py label --images raw_images/ --teacher best.pt

  # Step 2: Train nano student on pseudo-labels
  python distill_yolov8n.py train

  # Step 3: Export to ONNX
  python distill_yolov8n.py export

  # Or run everything:
  python distill_yolov8n.py full --images raw_images/ --teacher best.pt

Image collection tips:
  - Take photos of each card type (ehliyet, pasaport, ogrenci_karti, tc_kimlik, akademisyen_karti)
  - Vary: angle, lighting, distance, background, partial occlusion
  - Aim for 50-100 images per class (250-500 total)
  - Include negative images (no cards) for robustness
  - Mix portrait and landscape orientations
"""

import argparse
import os
import shutil
import sys
from pathlib import Path


CLASSES = ["ehliyet", "pasaport", "ogrenci_karti", "tc_kimlik", "akademisyen_karti"]
DISTILL_DIR = Path("distillation_dataset")


def generate_pseudo_labels(
    images_dir: str,
    teacher_path: str = "app/core/card_type_model/best.pt",
    conf_threshold: float = 0.4,
    output_dir: Path = DISTILL_DIR,
):
    """
    Run the teacher model on unlabeled images to generate YOLO-format labels.
    High-confidence predictions become training labels for the student.
    """
    from ultralytics import YOLO
    import random

    images_path = Path(images_dir)
    if not images_path.exists():
        print(f"ERROR: Images directory '{images_dir}' not found")
        print("\nPlease collect card images into a directory. Tips:")
        print("  - Take photos of each card type from various angles")
        print("  - Aim for 50-100 images per class")
        print("  - Include varied lighting and backgrounds")
        sys.exit(1)

    # Load teacher model
    print(f"Loading teacher model from {teacher_path}...")
    teacher = YOLO(teacher_path)
    print(f"Teacher classes: {teacher.names}")

    # Find all images
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    all_images = [
        f for f in images_path.rglob("*")
        if f.suffix.lower() in exts
    ]
    print(f"Found {len(all_images)} images")

    if len(all_images) == 0:
        print("No images found. Add card images to the directory and try again.")
        sys.exit(1)

    # Create output directories
    for split in ["train", "val"]:
        (output_dir / split / "images").mkdir(parents=True, exist_ok=True)
        (output_dir / split / "labels").mkdir(parents=True, exist_ok=True)

    # Shuffle and split 85/15
    random.shuffle(all_images)
    split_idx = int(len(all_images) * 0.85)
    splits = {
        "train": all_images[:split_idx],
        "val": all_images[split_idx:],
    }

    stats = {"total": 0, "labeled": 0, "skipped": 0, "per_class": {c: 0 for c in CLASSES}}

    for split_name, images in splits.items():
        print(f"\nProcessing {split_name} split ({len(images)} images)...")
        for img_path in images:
            stats["total"] += 1

            # Run teacher inference
            results = teacher(str(img_path), conf=conf_threshold, verbose=False)
            result = results[0]

            if len(result.boxes) == 0:
                stats["skipped"] += 1
                continue

            # Generate YOLO-format label file
            img_h, img_w = result.orig_shape
            label_lines = []

            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])

                if conf < conf_threshold:
                    continue

                # Convert xyxy to xywh normalized
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cx = ((x1 + x2) / 2) / img_w
                cy = ((y1 + y2) / 2) / img_h
                bw = (x2 - x1) / img_w
                bh = (y2 - y1) / img_h

                label_lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
                cls_name = teacher.names[cls_id]
                stats["per_class"][cls_name] = stats["per_class"].get(cls_name, 0) + 1

            if label_lines:
                # Copy image
                dest_img = output_dir / split_name / "images" / img_path.name
                shutil.copy2(img_path, dest_img)

                # Write label
                dest_label = output_dir / split_name / "labels" / (img_path.stem + ".txt")
                dest_label.write_text("\n".join(label_lines))

                stats["labeled"] += 1

    # Write data.yaml
    data_yaml = output_dir / "data.yaml"
    data_yaml.write_text(f"""# Auto-generated pseudo-labels from YOLOv8m teacher
# Teacher confidence threshold: {conf_threshold}

train: train/images
val: val/images

nc: {len(CLASSES)}
names: {CLASSES}
""")

    print(f"\n{'='*60}")
    print(f"Pseudo-labeling complete!")
    print(f"  Total images: {stats['total']}")
    print(f"  Labeled: {stats['labeled']}")
    print(f"  Skipped (no detections): {stats['skipped']}")
    print(f"  Per-class detections: {stats['per_class']}")
    print(f"  Output: {output_dir}/")
    print(f"  data.yaml: {data_yaml}")
    print(f"{'='*60}")

    return output_dir


def train_student(
    dataset_path: str = str(DISTILL_DIR / "data.yaml"),
    epochs: int = 80,
    batch: int = 16,
    imgsz: int = 640,
    device: str = "0",
):
    """Train YOLOv8n student on pseudo-labeled data."""
    from ultralytics import YOLO

    data_path = Path(dataset_path)
    if not data_path.exists():
        print(f"ERROR: Dataset not found at '{dataset_path}'")
        print("Run 'python distill_yolov8n.py label' first to generate pseudo-labels")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Training YOLOv8n Student (Knowledge Distillation)")
    print(f"{'='*60}")

    model = YOLO("yolov8n.pt")

    results = model.train(
        data=dataset_path,
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device=device,
        project="runs/detect",
        name="card_nano_distilled",
        exist_ok=True,
        # Use slightly gentler training for pseudo-labels
        lr0=0.003,
        lrf=0.01,
        cos_lr=True,
        warmup_epochs=5.0,
        patience=25,
        # Less aggressive augmentation since pseudo-labels may have noise
        mosaic=0.7,
        mixup=0.05,
        scale=0.4,
        erasing=0.3,
        amp=True,
        workers=4,
        box=7.5,
        cls=0.5,
        dfl=1.5,
        close_mosaic=10,
    )

    print(f"\nStudent training complete!")
    return model, results


def export_student(
    model_path: str = "runs/detect/card_nano_distilled/weights/best.pt",
    imgsz: int = 640,
):
    """Export student model to ONNX."""
    from ultralytics import YOLO

    if not Path(model_path).exists():
        print(f"ERROR: Model not found at '{model_path}'")
        sys.exit(1)

    model = YOLO(model_path)

    onnx_path = model.export(
        format="onnx",
        imgsz=imgsz,
        simplify=True,
        opset=13,
        half=False,
        dynamic=False,
        batch=1,
    )

    size_mb = os.path.getsize(onnx_path) / (1024 * 1024)
    print(f"\nExported: {onnx_path} ({size_mb:.1f} MB)")
    print(f"Upload to Hostinger: /auth-test/card_model_nano.onnx")

    return onnx_path


def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Distillation: YOLOv8m -> YOLOv8n"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Label command
    label_parser = subparsers.add_parser("label", help="Generate pseudo-labels with teacher")
    label_parser.add_argument("--images", required=True, help="Path to unlabeled card images")
    label_parser.add_argument(
        "--teacher", default="app/core/card_type_model/best.pt",
        help="Path to teacher model (YOLOv8m best.pt)"
    )
    label_parser.add_argument("--conf", type=float, default=0.4, help="Confidence threshold")

    # Train command
    train_parser = subparsers.add_parser("train", help="Train nano student")
    train_parser.add_argument("--data", default=str(DISTILL_DIR / "data.yaml"))
    train_parser.add_argument("--epochs", type=int, default=80)
    train_parser.add_argument("--batch", type=int, default=16)
    train_parser.add_argument("--imgsz", type=int, default=640)
    train_parser.add_argument("--device", default="0")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export student to ONNX")
    export_parser.add_argument(
        "--model", default="runs/detect/card_nano_distilled/weights/best.pt"
    )

    # Full pipeline
    full_parser = subparsers.add_parser("full", help="Label + train + export")
    full_parser.add_argument("--images", required=True)
    full_parser.add_argument("--teacher", default="app/core/card_type_model/best.pt")
    full_parser.add_argument("--conf", type=float, default=0.4)
    full_parser.add_argument("--epochs", type=int, default=80)
    full_parser.add_argument("--device", default="0")

    args = parser.parse_args()

    if args.command == "label":
        generate_pseudo_labels(args.images, args.teacher, args.conf)
    elif args.command == "train":
        train_student(args.data, args.epochs, args.batch, args.imgsz, args.device)
    elif args.command == "export":
        export_student(args.model)
    elif args.command == "full":
        generate_pseudo_labels(args.images, args.teacher, args.conf)
        train_student(epochs=args.epochs, device=args.device)
        export_student()
    else:
        parser.print_help()
        print("\nQuick start:")
        print("  1. Collect 250-500 card images into raw_images/")
        print("  2. python distill_yolov8n.py full --images raw_images/")
        print("  3. Upload best.onnx to Hostinger /auth-test/card_model_nano.onnx")


if __name__ == "__main__":
    main()
