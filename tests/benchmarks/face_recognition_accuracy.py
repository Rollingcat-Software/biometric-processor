#!/usr/bin/env python3
"""Face-recognition verification benchmark harness (LFW / AgeDB-30 / CFP-FP).

Reproducible 1:1 verification eval for the production face model (FaceNet-512 via
DeepFace), so the accuracy numbers reported on the poster / in the defense are
backed by a committed, re-runnable script + a raw per-pair CSV.

It does NOT run in CI (no datasets in-repo, not a ``test_*`` file). It is a CLI
tool the team runs locally against a standard verification protocol, then commits
the resulting CSV next to ``RESULTS.md``.

Pairs file format (one pair per line, whitespace-separated)::

    <img_path_a> <img_path_b> <label>     # label = 1 genuine / 0 impostor

(LFW's ``pairs.txt`` can be converted to this form; ``--images`` is prepended.)

Example::

    python tests/benchmarks/face_recognition_accuracy.py \
        --pairs lfw_pairs.txt --images ~/datasets/lfw \
        --model Facenet512 --threshold 0.45 --out lfw_results.csv

Outputs AUC, EER, and FAR/TAR at the chosen cosine threshold, plus a per-pair CSV.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    a = a / (np.linalg.norm(a) + 1e-10)
    b = b / (np.linalg.norm(b) + 1e-10)
    return float(1.0 - np.dot(a, b))


def embed(img_path: str, model: str) -> np.ndarray:
    # Imported lazily so --help works without the heavy ML stack installed.
    from deepface import DeepFace

    reps = DeepFace.represent(
        img_path=img_path, model_name=model,
        detector_backend="mtcnn", enforce_detection=False,
    )
    return np.asarray(reps[0]["embedding"], dtype=np.float32)


def equal_error_rate(labels: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    """EER + the threshold where FAR == FRR. ``scores`` = genuine-similarity (higher = more same)."""
    from sklearn.metrics import roc_curve

    fpr, tpr, thr = roc_curve(labels, scores)
    fnr = 1 - tpr
    i = int(np.nanargmin(np.abs(fnr - fpr)))
    return float((fpr[i] + fnr[i]) / 2), float(thr[i])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pairs", required=True, help="pairs file: 'imgA imgB label' per line")
    ap.add_argument("--images", default="", help="root dir prepended to relative image paths")
    ap.add_argument("--model", default="Facenet512", help="DeepFace model (prod = Facenet512)")
    ap.add_argument("--threshold", type=float, default=0.45, help="cosine-distance accept threshold")
    ap.add_argument("--out", default="face_recognition_results.csv", help="per-pair CSV output")
    args = ap.parse_args(argv)

    root = Path(args.images)
    rows, labels, dists = [], [], []
    cache: dict[str, np.ndarray] = {}

    for ln in Path(args.pairs).read_text().splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        a, b, label = ln.split()
        pa, pb = str(root / a), str(root / b)
        try:
            ea = cache.setdefault(pa, embed(pa, args.model))
            eb = cache.setdefault(pb, embed(pb, args.model))
        except Exception as exc:  # noqa: BLE001 — a missing/undetectable face shouldn't abort the run
            print(f"skip {a} {b}: {exc}", file=sys.stderr)
            continue
        d = cosine_distance(ea, eb)
        labels.append(int(label)); dists.append(d)
        rows.append({"img_a": a, "img_b": b, "label": int(label),
                     "cosine_distance": round(d, 6), "accept": int(d <= args.threshold)})

    if not labels:
        print("no usable pairs", file=sys.stderr)
        return 2

    from sklearn.metrics import roc_auc_score

    labels_np = np.asarray(labels)
    sim = 1.0 - np.asarray(dists)                       # similarity: higher = same person
    auc = float(roc_auc_score(labels_np, sim))
    eer, eer_thr = equal_error_rate(labels_np, sim)
    accept = np.asarray(dists) <= args.threshold
    genuine, impostor = labels_np == 1, labels_np == 0
    tar = float(accept[genuine].mean()) if genuine.any() else float("nan")   # true accept
    far = float(accept[impostor].mean()) if impostor.any() else float("nan")  # false accept

    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["img_a", "img_b", "label", "cosine_distance", "accept"])
        w.writeheader(); w.writerows(rows)

    print(f"model={args.model}  pairs={len(labels)}  (genuine={int(genuine.sum())} impostor={int(impostor.sum())})")
    print(f"AUC={auc:.4f}  EER={eer*100:.2f}%  (EER cos-sim thr={eer_thr:.3f})")
    print(f"@cosine<= {args.threshold}:  TAR={tar*100:.2f}%  FAR={far*100:.2f}%")
    print(f"per-pair CSV -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
