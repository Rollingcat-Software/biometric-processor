#!/usr/bin/env python3
"""Export + quantize DeepFace Facenet512 to ONNX from our pinned weights.

This produces the *shippable client model* for the browser-side face-embedding
path (compute the 512-d Facenet512 embedding in the browser via
onnxruntime-web, upload only the vector). It is built from the SAME
SHA-pinned weights the server already runs
(``~/.deepface/weights/facenet512_weights.h5``) so the exported model matches
the production DeepFace Facenet512 exactly -- no unlicensed third-party ONNX.

Pipeline:
  1. Build the DeepFace Facenet512 Keras model (loads the pinned .h5).
  2. Export -> ONNX via tf2onnx (opset 17, input (1,160,160,3) float32 NHWC).
  3. INT8-quantize via onnxruntime.quantization.quantize_dynamic (QInt8)
     -> the shippable ~24 MB model.
  4. Parity-check the quantized model vs DeepFace.represent(Facenet512) on the
     sample faces -- cosine should stay >= ~0.99. If INT8 parity regresses
     below --min-cos, fall back to FP16 (~47 MB) automatically.
  5. Print the shipped model's sha256 + byte size.

The model lands OUTSIDE git (default /tmp/fnet_out); the repo gitignores
``*.onnx``. Only this script is version-controlled -- the model is a
reproducible build artifact.

Model preprocessing contract the browser must reproduce (see the spike report
``docs/THESIS_AUDIT_2026-06-11/16_facenet_browser_spike.md``):
  input (1,160,160,3) float32, BGR, [0,1], aspect-preserving resize +
  centre black-pad to 160x160, normalization="base" (identity);
  output 512-d, L2-normalize before upload.

Usage:
  python scripts/export_facenet512_onnx.py                 # INT8, parity on samples
  python scripts/export_facenet512_onnx.py --out /models   # custom out dir
  python scripts/export_facenet512_onnx.py --format fp16    # force FP16
  python scripts/export_facenet512_onnx.py --no-parity      # skip parity (no faces)

Requires: deepface, tensorflow(-cpu), tf2onnx, onnx, onnxruntime
(see requirements-known-good-2026-05-29.lock). The feasibility spike used the
isolated venv at /tmp/fnet_spike/venv which has all of these.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import os
import sys
import time

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

DEFAULT_FACES_GLOB = "/tmp/fnet_spike/faces/*.jpg"
MIN_PARITY_COS = 0.98  # below this for INT8 -> auto-fallback to FP16


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_keras_model():
    """Build the DeepFace Facenet512 Keras model (loads pinned weights)."""
    from deepface.modules import modeling

    client = modeling.build_model(
        task="facial_recognition", model_name="Facenet512"
    )
    return client.model  # underlying tf.keras Model


def export_fp32_onnx(keras_model, out_path: str) -> None:
    """Export the Keras model to FP32 ONNX (opset 17, fixed batch=1 input)."""
    import tensorflow as tf
    import tf2onnx

    spec = (tf.TensorSpec((1, 160, 160, 3), tf.float32, name="input"),)
    tf2onnx.convert.from_keras(
        keras_model, input_signature=spec, opset=17, output_path=out_path
    )


def quantize_int8(fp32_path: str, int8_path: str) -> None:
    """Dynamic INT8 (QInt8) quantization via onnxruntime.quantization."""
    from onnxruntime.quantization import QuantType, quantize_dynamic

    quantize_dynamic(
        model_input=fp32_path,
        model_output=int8_path,
        weight_type=QuantType.QInt8,
    )


def quantize_fp16(fp32_path: str, fp16_path: str) -> None:
    """FP16 conversion. Prefer onnxconverter-common; fall back to onnxruntime
    float16 transformer if unavailable."""
    import onnx

    model = onnx.load(fp32_path)
    try:
        from onnxconverter_common import float16

        model_fp16 = float16.convert_float_to_float16(
            model, keep_io_types=True
        )
    except ImportError:
        from onnxruntime.transformers.float16 import convert_float_to_float16

        model_fp16 = convert_float_to_float16(model, keep_io_types=True)
    onnx.save(model_fp16, fp16_path)


# ---------------------------------------------------------------- parity check
def _load_faces(faces_glob: str):
    import cv2

    faces = {}
    for f in sorted(glob.glob(faces_glob)):
        img = cv2.imread(f)
        if img is not None:
            faces[os.path.basename(f).rsplit(".", 1)[0]] = img
    return faces


def parity_check(onnx_path: str, faces_glob: str) -> dict:
    """Compare the ONNX model's embeddings vs DeepFace Facenet512 on sample
    faces. Mirrors the production path: detector_backend='skip',
    aspect-preserving resize + centre-pad to 160x160, [0,1], normalization=
    'base' -- and feeds the model BGR (the colour order DeepFace's
    represent() hands to Facenet512; see spike report sec.1). Returns
    {name: cosine}.

    NOTE: colour order is load-bearing. cv2.imread gives BGR and that is what
    the model expects; converting to RGB here collapses parity to ~0.86-0.95
    (this exact bug was in the spike's first harness). Do NOT add a
    BGR->RGB conversion.
    """
    import numpy as np
    import onnxruntime as ort
    from deepface import DeepFace
    from deepface.modules import preprocessing

    faces = _load_faces(faces_glob)
    if not faces:
        print(f"[parity] no faces matched {faces_glob}; skipping parity")
        return {}

    sess = ort.InferenceSession(
        onnx_path, providers=["CPUExecutionProvider"]
    )
    inp_name = sess.get_inputs()[0].name

    def onnx_embed(face_bgr):
        # feed BGR directly (production colour order), aspect-preserving
        # resize + centre-pad to 160x160, [0,1], base-norm (identity).
        x = preprocessing.resize_image(face_bgr, (160, 160))
        x = preprocessing.normalize_input(x, normalization="base")
        out = sess.run(None, {inp_name: x.astype(np.float32)})[0][0]
        n = np.linalg.norm(out)
        return out / n if n else out

    def deepface_embed(face_bgr):
        objs = DeepFace.represent(
            img_path=face_bgr,
            model_name="Facenet512",
            detector_backend="skip",
            enforce_detection=False,
            align=True,
            normalization="base",
        )
        e = np.array(objs[0]["embedding"], dtype=np.float32)
        n = np.linalg.norm(e)
        return e / n if n else e

    parity = {}
    for name, img in faces.items():
        d = deepface_embed(img)
        o = onnx_embed(img)
        parity[name] = round(
            float(np.dot(d, o) / (np.linalg.norm(d) * np.linalg.norm(o))), 5
        )
        print(f"[parity] {name}: cos(deepface, onnx) = {parity[name]}")
    if parity:
        vals = list(parity.values())
        print(
            f"[parity] MEAN={round(sum(vals) / len(vals), 5)} "
            f"MIN={round(min(vals), 5)}"
        )
    return parity


def report(label: str, path: str) -> None:
    size = os.path.getsize(path)
    print(f"\n=== SHIPPABLE MODEL ({label}) ===")
    print(f"path   : {path}")
    print(f"bytes  : {size} ({size / 1e6:.2f} MB)")
    print(f"sha256 : {sha256_of(path)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out", default="/tmp/fnet_out",
        help="output dir for the .onnx artifacts (default /tmp/fnet_out)",
    )
    ap.add_argument(
        "--format", choices=["int8", "fp16", "fp32"], default="int8",
        help="quantization format for the shipped model (default int8; "
             "auto-falls back to fp16 if int8 parity < --min-cos)",
    )
    ap.add_argument(
        "--faces", default=DEFAULT_FACES_GLOB,
        help=f"glob of sample face jpgs for parity (default {DEFAULT_FACES_GLOB})",
    )
    ap.add_argument(
        "--no-parity", action="store_true",
        help="skip the DeepFace parity check (e.g. no sample faces available)",
    )
    ap.add_argument(
        "--min-cos", type=float, default=MIN_PARITY_COS,
        help=f"min acceptable INT8 parity cosine before FP16 fallback "
             f"(default {MIN_PARITY_COS})",
    )
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    fp32_path = os.path.join(args.out, "facenet512.onnx")
    int8_path = os.path.join(args.out, "facenet512_int8.onnx")
    fp16_path = os.path.join(args.out, "facenet512_fp16.onnx")

    # 1. build + 2. FP32 export (always needed as the quantization source) -----
    t0 = time.time()
    keras_model = build_keras_model()
    print(
        f"[build] Facenet512 Keras model: params={keras_model.count_params():,} "
        f"input={keras_model.inputs[0].shape} ({time.time() - t0:.1f}s)"
    )

    t0 = time.time()
    export_fp32_onnx(keras_model, fp32_path)
    print(
        f"[onnx] FP32 export OK opset17 -> {fp32_path} "
        f"({os.path.getsize(fp32_path) / 1e6:.1f} MB, {time.time() - t0:.1f}s)"
    )

    # 3. quantize to the requested shippable format ---------------------------
    if args.format == "fp32":
        shipped_path, shipped_label = fp32_path, "FP32"
    elif args.format == "fp16":
        quantize_fp16(fp32_path, fp16_path)
        shipped_path, shipped_label = fp16_path, "FP16"
        print(f"[onnx] FP16 -> {fp16_path}")
    else:  # int8
        quantize_int8(fp32_path, int8_path)
        shipped_path, shipped_label = int8_path, "INT8"
        print(f"[onnx] INT8 (QInt8 dynamic) -> {int8_path}")

    # 4. parity check (+ auto FP16 fallback if INT8 regresses) ----------------
    if not args.no_parity:
        parity = parity_check(shipped_path, args.faces)
        if (
            args.format == "int8"
            and parity
            and min(parity.values()) < args.min_cos
        ):
            print(
                f"[parity] INT8 MIN={min(parity.values())} < {args.min_cos} "
                f"-> falling back to FP16"
            )
            quantize_fp16(fp32_path, fp16_path)
            shipped_path, shipped_label = fp16_path, "FP16 (INT8-fallback)"
            print(f"[onnx] FP16 -> {fp16_path}")
            parity_check(shipped_path, args.faces)

    # 5. final report ---------------------------------------------------------
    report(shipped_label, shipped_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
