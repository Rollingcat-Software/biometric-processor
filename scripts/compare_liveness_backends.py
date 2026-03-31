"""Compare liveness backend scores on local fixture images.

Usage:
    .\.venv\Scripts\python.exe scripts\compare_liveness_backends.py
    .\.venv\Scripts\python.exe scripts\compare_liveness_backends.py --limit 20
    .\.venv\Scripts\python.exe scripts\compare_liveness_backends.py --images path\to\img1.jpg path\to\img2.jpg

This script is intended for local evaluation before enabling UniFace in production.
It compares the currently implemented "enhanced" and "uniface" backends on the same
images and prints a compact score table plus simple averages.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from statistics import mean
from typing import Iterable

import cv2

from app.domain.exceptions.face_errors import FaceNotDetectedError
from app.infrastructure.ml.liveness.enhanced_liveness_detector import EnhancedLivenessDetector
from app.infrastructure.ml.liveness.uniface_liveness_detector import UniFaceLivenessDetector


FIXTURES_DIR = Path("tests/fixtures/images")


def collect_images(paths: list[str] | None, limit: int) -> list[Path]:
    if paths:
        resolved = [Path(p) for p in paths]
        return [p for p in resolved if p.is_file()]

    exts = {".jpg", ".jpeg", ".png", ".webp"}
    images = sorted(
        p for p in FIXTURES_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() in exts
    )
    return images[:limit]


async def compare_one(image_path: Path) -> dict:
    image = cv2.imread(str(image_path))
    if image is None:
        return {
            "image": str(image_path),
            "error": "failed_to_load",
        }

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

    if len(faces) == 0:
        return {
            "image": str(image_path),
            "error": "no_face_detected",
        }

    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    face_crop = image[y:y+h, x:x+w]

    enhanced = EnhancedLivenessDetector(liveness_threshold=70.0)
    uniface = UniFaceLivenessDetector(liveness_threshold=70.0)

    try:
        enhanced_result = await enhanced.check_liveness(face_crop)
        enhanced_error = None
    except FaceNotDetectedError as exc:
        enhanced_result = None
        enhanced_error = str(exc)

    try:
        uniface_result = await uniface.check_liveness(face_crop)
        uniface_error = None
    except Exception as exc:
        uniface_result = None
        uniface_error = str(exc)

    return {
        "image": str(image_path),
        "enhanced_score": None if enhanced_result is None else enhanced_result.liveness_score,
        "enhanced_live": None if enhanced_result is None else enhanced_result.is_live,
        "enhanced_details": None if enhanced_result is None else enhanced_result.details,
        "enhanced_error": enhanced_error,
        "uniface_score": None if uniface_result is None else uniface_result.liveness_score,
        "uniface_live": None if uniface_result is None else uniface_result.is_live,
        "uniface_details": None if uniface_result is None else uniface_result.details,
        "uniface_error": uniface_error,
    }


def print_report(results: Iterable[dict]) -> None:
    results = list(results)
    print("image,enhanced_score,enhanced_live,enhanced_error,uniface_score,uniface_live,uniface_error")
    for row in results:
        print(
            f"{row['image']},"
            f"{row.get('enhanced_score')},"
            f"{row.get('enhanced_live')},"
            f"{row.get('enhanced_error')},"
            f"{row.get('uniface_score')},"
            f"{row.get('uniface_live')},"
            f"{row.get('uniface_error')}"
        )

    enhanced_scores = [r["enhanced_score"] for r in results if r.get("enhanced_score") is not None]
    uniface_scores = [r["uniface_score"] for r in results if r.get("uniface_score") is not None]

    print()
    print(f"images_tested={len(results)}")
    print(f"enhanced_avg_score={mean(enhanced_scores):.2f}" if enhanced_scores else "enhanced_avg_score=n/a")
    print(f"uniface_avg_score={mean(uniface_scores):.2f}" if uniface_scores else "uniface_avg_score=n/a")
    print(f"uniface_success_count={len(uniface_scores)}")


def save_report(results: Iterable[dict], output_path: str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(list(results), indent=2), encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10, help="Max number of fixture images to test")
    parser.add_argument("--images", nargs="*", help="Explicit image paths to test")
    parser.add_argument(
        "--output",
        help="Optional JSON file to store per-image comparison results for audit/benchmark tracking",
    )
    args = parser.parse_args()

    images = collect_images(args.images, args.limit)
    if not images:
        raise SystemExit("No images found to compare.")

    results = []
    for image_path in images:
        results.append(await compare_one(image_path))

    print_report(results)
    if args.output:
        save_report(results, args.output)


if __name__ == "__main__":
    asyncio.run(main())
