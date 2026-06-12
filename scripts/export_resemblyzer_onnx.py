#!/usr/bin/env python3
"""Export the Resemblyzer VoiceEncoder (GE2E speaker encoder) to ONNX.

This produces the *shippable client model* for the browser-side voice-embedding
path (compute the 256-d speaker embedding in the browser via onnxruntime-web,
upload only the vector -- the raw audio never leaves the device). It is built
from the SAME pretrained weights the server already runs
(``resemblyzer/pretrained.pt``, the ~17 MB GE2E LSTM encoder baked into the bio
image) so the exported model matches the production Resemblyzer encoder exactly.

The model itself is tiny and trivially exportable: a 3-layer LSTM
(input 40-channel mel, hidden 256) -> Linear(256->256) -> ReLU -> L2-normalize.
``forward(mels)`` maps a batch of mel spectrograms of shape
``(batch, n_frames, 40)`` to ``(batch, 256)`` unit-norm partial embeddings.

  *** PREPROCESSING IS THE HARD PART, NOT THE MODEL. ***
The browser MUST reproduce Resemblyzer's exact audio preprocessing to get a
matching embedding (see ``docs/design/VOICE_CLIENT_EMBEDDING_SPEC.md`` for the
precise, load-bearing contract). The two costly pieces are:
  1. ``preprocess_wav`` -- dBFS volume normalization (increase-only to -30 dBFS)
     + ``trim_long_silences`` (WebRTC VAD mode 3, 30 ms windows, 8-frame moving
     average, dilation by ``vad_max_silence_length+1``). webrtcvad is a C
     extension; a JS port is approximate and MUST be validated before trust.
  2. ``wav_to_mel_spectrogram`` -- librosa.feature.melspectrogram with
     n_fft=400, hop=160, n_mels=40, sr=16000 (NOT a log-mel; raw power mel).
  3. ``embed_utterance`` -- split into 1.6 s (160-frame) partials at rate=1.3
     with min_coverage=0.75, run each through the model, then L2-norm the MEAN
     of the partial embeddings.

This script exports ONLY the neural net (step: mels -> 256-d). The partial
slicing + mean + final L2-norm of ``embed_utterance`` and ALL of the audio
preprocessing must be reproduced in JS (or done with a second small ONNX/DSP
path). The exported model has a DYNAMIC ``n_frames`` axis so the browser can
feed either a single 160-frame partial or batch all partials at once.

Pipeline:
  1. Load the Resemblyzer ``VoiceEncoder`` (loads the pinned ``pretrained.pt``).
  2. ``torch.onnx.export`` -> ONNX (opset 17, input (B, n_frames, 40) float32,
     dynamic batch + n_frames).
  3. Parity-check the ONNX model vs the torch ``forward`` on random + real mel
     batches (cosine should be >= ~0.9999). Optionally end-to-end vs
     ``embed_utterance`` on a sample wav if one is provided.
  4. Print the shipped model's sha256 + byte size.

The model lands OUTSIDE git (default /tmp/voice_out); the repo gitignores
``*.onnx``/``*.pt``. Only this script is version-controlled -- the model is a
reproducible build artifact, hosted at app.fivucsas.com/models/ alongside
facenet512 (see docs/design/VOICE_CLIENT_EMBEDDING_SPEC.md "Model delivery").

Usage (inside the bio Docker image, which has resemblyzer + torch + onnx):
  python scripts/export_resemblyzer_onnx.py
  python scripts/export_resemblyzer_onnx.py --out /models
  python scripts/export_resemblyzer_onnx.py --wav /tmp/sample.wav   # e2e parity
  python scripts/export_resemblyzer_onnx.py --opset 17

Requires: torch, resemblyzer, onnx, onnxruntime (all in
requirements-known-good-2026-05-29.lock / the bio image). Run with:
  docker run --rm -v "$PWD/scripts:/scripts:ro" -v /tmp/voice_out:/out \\
      --entrypoint python <bio-image> /scripts/export_resemblyzer_onnx.py --out /out
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time

# Resemblyzer's mel input dimensionality + model output size (hparams.py).
MEL_N_CHANNELS = 40
EMBEDDING_DIM = 256
# A single partial utterance is 160 frames (1.6 s); a representative export
# sample shape. The exported graph keeps n_frames dynamic.
PARTIAL_N_FRAMES = 160
MIN_PARITY_COS = 0.999


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_encoder():
    """Load the Resemblyzer VoiceEncoder on CPU (loads the pinned weights)."""
    import torch
    from resemblyzer import VoiceEncoder

    encoder = VoiceEncoder(device="cpu", verbose=True)
    encoder.eval()
    # forward() uses no_grad-free LSTM; ensure inference mode for export.
    for p in encoder.parameters():
        p.requires_grad_(False)
    return encoder, torch


def export_onnx(encoder, torch, out_path: str, opset: int) -> None:
    """Export VoiceEncoder.forward (mels -> 256-d) to ONNX with dynamic axes."""
    # (batch=1, n_frames=160, 40) representative input. The TorchScript ONNX
    # exporter warns that a variable-length LSTM exported with batch>1 can fail
    # at a different runtime batch size unless h0/c0 are graph inputs; exporting
    # at batch=1 (with n_frames still dynamic) sidesteps that entirely. The
    # browser runs one partial utterance per inference (or loops), so batch=1 is
    # the real client shape anyway.
    dummy = torch.randn(1, PARTIAL_N_FRAMES, MEL_N_CHANNELS, dtype=torch.float32)
    # dynamo=False -> the legacy TorchScript ONNX exporter, which has no
    # onnxscript dependency and handles the dynamic-axes LSTM cleanly. (torch
    # 2.11's default dynamo exporter needs the optional ``onnxscript`` package,
    # which is not in the bio image's pinned deps.)
    torch.onnx.export(
        encoder,
        dummy,
        out_path,
        export_params=True,
        opset_version=opset,
        do_constant_folding=True,
        input_names=["mels"],
        output_names=["embeds"],
        dynamic_axes={
            "mels": {0: "batch", 1: "n_frames"},
            "embeds": {0: "batch"},
        },
        dynamo=False,
    )


def _cos(a, b) -> float:
    import numpy as np

    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def parity_check(onnx_path: str, encoder, torch, wav_path: str | None) -> dict:
    """Compare ONNX vs torch ``forward`` on random mel batches, plus an optional
    end-to-end ``embed_utterance`` comparison on a real wav.

    Returns a dict of {case: min_cosine}. The model is deterministic, so parity
    should be ~1.0 (>= MIN_PARITY_COS); a regression means the export is wrong
    and the client port MUST NOT be trusted.
    """
    import numpy as np
    import onnxruntime as ort

    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name

    results: dict[str, float] = {}

    # --- random-mel batches (varied n_frames + batch) ------------------------
    rng = np.random.default_rng(1234)
    cos_min = 1.0
    for batch, n_frames in [(1, 160), (3, 160), (1, 80), (5, 200)]:
        mels = rng.standard_normal((batch, n_frames, MEL_N_CHANNELS)).astype(np.float32)
        with torch.no_grad():
            t_out = encoder(torch.from_numpy(mels)).cpu().numpy()
        o_out = sess.run(None, {inp: mels})[0]
        for i in range(batch):
            cos_min = min(cos_min, _cos(t_out[i], o_out[i]))
    results["random_mels"] = round(cos_min, 6)
    print(f"[parity] random_mels MIN cos(torch, onnx) = {results['random_mels']}")

    # --- end-to-end on a real wav (optional) ---------------------------------
    if wav_path:
        from resemblyzer import preprocess_wav
        from resemblyzer.audio import wav_to_mel_spectrogram

        wav = preprocess_wav(wav_path)
        # Reproduce embed_utterance's partial slicing, but run the ONNX model
        # for the partials and compare to the torch embed_utterance result.
        ref_embed = encoder.embed_utterance(wav)

        wav_slices, mel_slices = encoder.compute_partial_slices(len(wav), rate=1.3, min_coverage=0.75)
        max_wave_length = wav_slices[-1].stop
        if max_wave_length >= len(wav):
            wav = np.pad(wav, (0, max_wave_length - len(wav)), "constant")
        mel = wav_to_mel_spectrogram(wav)
        mels = np.array([mel[s] for s in mel_slices]).astype(np.float32)
        partial_embeds = sess.run(None, {inp: mels})[0]
        raw = np.mean(partial_embeds, axis=0)
        onnx_embed = raw / np.linalg.norm(raw, 2)
        results["e2e_embed_utterance"] = round(_cos(ref_embed, onnx_embed), 6)
        print(
            f"[parity] e2e_embed_utterance cos(torch, onnx) = "
            f"{results['e2e_embed_utterance']}"
        )

    return results


def report(path: str) -> None:
    size = os.path.getsize(path)
    print("\n=== SHIPPABLE MODEL (Resemblyzer VoiceEncoder, FP32) ===")
    print(f"path   : {path}")
    print(f"bytes  : {size} ({size / 1e6:.2f} MB)")
    print(f"sha256 : {sha256_of(path)}")
    print(
        "\nNEXT: host this at app.fivucsas.com/models/ as "
        "resemblyzer-<sha256>.onnx and set DEFAULT_VOICE_MODEL_URL/SHA256 + the "
        "public/models/manifest.json entry in web-app. See "
        "docs/design/VOICE_CLIENT_EMBEDDING_SPEC.md."
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out", default="/tmp/voice_out",
        help="output dir for the .onnx artifact (default /tmp/voice_out)",
    )
    ap.add_argument(
        "--opset", type=int, default=17,
        help="ONNX opset version (default 17; LSTM is well-supported >= 14)",
    )
    ap.add_argument(
        "--wav", default=None,
        help="optional path to a 16 kHz sample wav for end-to-end parity vs "
             "embed_utterance",
    )
    ap.add_argument(
        "--min-cos", type=float, default=MIN_PARITY_COS,
        help=f"min acceptable parity cosine (default {MIN_PARITY_COS})",
    )
    ap.add_argument(
        "--no-parity", action="store_true",
        help="skip the torch<->onnx parity check",
    )
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    onnx_path = os.path.join(args.out, "resemblyzer_voice_encoder.onnx")

    t0 = time.time()
    encoder, torch = build_encoder()
    n_params = sum(p.numel() for p in encoder.parameters())
    print(f"[build] VoiceEncoder loaded: params={n_params:,} ({time.time() - t0:.1f}s)")

    t0 = time.time()
    export_onnx(encoder, torch, onnx_path, args.opset)
    print(
        f"[onnx] export OK opset{args.opset} -> {onnx_path} "
        f"({os.path.getsize(onnx_path) / 1e6:.2f} MB, {time.time() - t0:.1f}s)"
    )

    if not args.no_parity:
        parity = parity_check(onnx_path, encoder, torch, args.wav)
        worst = min(parity.values()) if parity else 1.0
        if worst < args.min_cos:
            print(
                f"[parity] FAIL: worst cosine {worst} < {args.min_cos}. "
                f"The export is NOT faithful -- do not ship.",
                file=sys.stderr,
            )
            return 1
        print(f"[parity] OK: worst cosine {worst} >= {args.min_cos}")

    report(onnx_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
