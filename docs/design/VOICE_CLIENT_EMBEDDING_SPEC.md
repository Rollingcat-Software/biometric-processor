# GPU-less VOICE embedding — preprocessing + model contract (audit H3)

**Status (2026-06-12):** Server endpoints + ONNX export are DONE and VERIFIED.
The browser preprocessing port is SPEC'd here but NOT yet verified to parity —
the web-app voice-embedding module ships as a **documented scaffold behind a
default-OFF flag**. Read "Honesty / completeness" at the bottom before enabling.

This is the load-bearing contract the browser MUST reproduce so a client-computed
256-d speaker embedding matches the server's. Getting any step wrong silently
produces a vector that fails to match the enrolled template (or, worse, weakly
matches the wrong person). Do not enable the client path until each step here is
validated against the Python reference.

---

## What this replaces

Today VOICE login + enroll send raw base64 audio to the bio service, which runs
the pretrained **Resemblyzer GE2E speaker encoder** (a ~17 MB torch 3-layer LSTM,
`resemblyzer/pretrained.pt`) on the CPU-only box to produce a 256-d embedding
(`app/infrastructure/ml/voice/speaker_embedder.py` → `embed_utterance`).

The GPU-less path moves that embedding into the browser: the audio never leaves
the device, only the 256-float vector is uploaded, and the server skips the
decode + VAD + forward pass. Flag-gated, default OFF (flag OFF = today's exact
server-side behaviour).

- Server endpoints (DONE): `POST /voice/verify-embedding`, `POST /voice/enroll-embedding`
  (`app/api/routes/voice.py`). They reuse the SAME pgvector cosine compare /
  centroid storage as `/voice/verify` + `/voice/enroll` run AFTER the embed step,
  just skipping the embed. Length-validated to exactly 256 (HTTP 422 otherwise).
- ONNX export (DONE + verified): `scripts/export_resemblyzer_onnx.py`.
- Identity Core gate: `app.auth.client-side-voice-embedding` (default OFF).
- Web flag: `VITE_CLIENT_SIDE_VOICE_EMBEDDING` (default OFF).

---

## The model

`VoiceEncoder.forward(mels) -> embeds` (resemblyzer `voice_encoder.py`):

```
mels  : float32 (batch, n_frames, 40)     # 40-channel mel spectrogram frames
  -> LSTM(input=40, hidden=256, num_layers=3, batch_first=True)
  -> take last layer's final hidden state h[-1]          (batch, 256)
  -> Linear(256 -> 256)
  -> ReLU
  -> L2-normalize over dim=1
embeds: float32 (batch, 256)              # positive, unit-norm partial embeddings
```

Exported ONNX (`scripts/export_resemblyzer_onnx.py`):
- input `mels` `(batch, n_frames, 40)` float32, **dynamic** batch + n_frames
- output `embeds` `(batch, 256)` float32
- opset 17, FP32, ~5.7 MB, exported from the SAME pinned `pretrained.pt` the
  server runs (1,423,616 params).
- **Verified:** torch-vs-ONNX cosine parity = **1.0** on random mel batches AND
  end-to-end vs `embed_utterance` on a sample wav (run the script with `--wav`).

> The model is exported at **batch=1** (n_frames dynamic) to avoid the
> TorchScript exporter's variable-length-LSTM-with-batch>1 caveat. The browser
> runs one partial utterance per inference (or loops over partials), which is the
> real client shape anyway. onnxruntime-web still accepts any batch on the
> dynamic axis, but feed batch=1 to stay on the proven path.

### Model delivery (mirror facenet512)
- Host the FP32 `.onnx` at `app.fivucsas.com/models/` as
  `resemblyzer-<sha256>.onnx` (same bucket as facenet512). FP32 is the ship
  format (the model is only 5.7 MB; do NOT INT8-quantize — onnxruntime-web WASM
  lacks the quant ops, same finding as facenet).
- In web-app set `DEFAULT_VOICE_MODEL_URL` / `DEFAULT_VOICE_MODEL_SHA256`
  constants + add a `public/models/manifest.json` entry **only after the file is
  actually hosted** — adding it before hosting FATALs the build (`fetch-models`),
  the exact failure facenet hit. While dark, fetch the model at RUNTIME only when
  the flag is ON.
- onnxruntime-web execution provider: `['wasm']` (mirror `FacenetEmbedder`),
  `wasmPaths` pinned to the jsdelivr ORT dist matching the web-app's
  `onnxruntime-web` version.

---

## The preprocessing the browser MUST reproduce

All constants are from resemblyzer `hparams.py`. **This is where parity is hard.**
The full reference chain is `preprocess_wav` → `wav_to_mel_spectrogram` →
`embed_utterance`'s partial slicing → model → mean + L2-norm.

### Step 0 — decode to 16 kHz mono float32 PCM in [-1, 1]
The web-app already produces this: `useVoiceRecorder` records WebM/Opus and
converts to **16 kHz mono 16-bit PCM WAV** via `encodeToWav16kMono`
(`src/features/auth/utils/audioToWav16k.ts`). Decode that WAV to a Float32Array
in [-1, 1]. `sampling_rate = 16000`.

### Step 1 — `preprocess_wav` (resemblyzer `audio.py`)
Two operations, in order:

**1a. Volume normalize (increase-only) to -30 dBFS** (`normalize_volume`):
```
int16_max = 32767
rms        = sqrt(mean((wav * int16_max)^2))
wave_dBFS  = 20 * log10(rms / int16_max)
dBFS_change = -30 - wave_dBFS
if dBFS_change < 0: return wav            # increase_only: never attenuate
return wav * (10 ^ (dBFS_change / 20))
```
Trivial to port exactly. Validate to ~1e-6.

**1b. `trim_long_silences` — WebRTC VAD silence trimming. ← THE HARD PART.**
```
samples_per_window = (30 * 16000) // 1000 = 480 samples (30 ms)
trim wav to a multiple of 480
pcm16 = round(wav * 32767) as int16
vad = webrtcvad.Vad(mode=3)               # AGGRESSIVE mode
for each 480-sample (30 ms) window: voice_flags.append(vad.is_speech(window, 16000))
# moving-average smooth, width = vad_moving_average_width = 8
audio_mask = round(moving_average(voice_flags, 8)).astype(bool)
# dilate voiced regions by (vad_max_silence_length + 1) = 7
audio_mask = binary_dilation(audio_mask, ones(7))
audio_mask = repeat(audio_mask, 480)      # back to sample resolution
return wav[audio_mask]
```
`webrtcvad` is a C extension wrapping Google's WebRTC GMM-based VAD; there is no
canonical JS port that is bit-exact. Options for the browser, in order of
preference:
  1. **A faithful WASM build of libwebrtc-vad** fed the identical 30 ms / mode-3
     frames, then reproduce the width-8 moving average + 7-wide dilation in JS.
     This is the only route that can be byte-exact; it MUST be validated frame-by-
     frame against the Python `voice_flags` array before trust.
  2. An energy/spectral VAD approximation — DOES NOT MATCH and measurably shifts
     the embedding (see "Honesty" below). Only acceptable if re-validated to keep
     same-speaker cosine comfortably above the 0.65 accept threshold across noisy
     real clips, which has NOT been done here.

### Step 2 — `wav_to_mel_spectrogram` (resemblyzer `audio.py`)
**NOT a log-mel — raw power mel.** Exactly `librosa.feature.melspectrogram`:
```
n_fft      = int(16000 * 25 / 1000) = 400      # 25 ms window
hop_length = int(16000 * 10 / 1000) = 160      # 10 ms hop
n_mels     = 40
sr         = 16000
return melspectrogram(y=wav, sr, n_fft, hop_length, n_mels).astype(float32).T
```
librosa defaults that MUST be matched (they are load-bearing):
- `win_length = n_fft = 400`, **Hann** window, `center=True` (reflect-pad by
  `n_fft//2`), `power=2.0` (power spectrogram).
- Mel filterbank: `htk=False` (Slaney mel scale), `norm='slueney'` (Slaney area
  normalization), `fmin=0.0`, `fmax=sr/2=8000`.
- Output transposed to `(n_frames, 40)`.
A JS STFT + Slaney mel filterbank must reproduce librosa's exact frame centering,
window, and mel-filter construction. Validate the mel matrix to a tight tolerance
against the Python reference on the same wav.

### Step 3 — partial slicing + mean + final L2-norm (`embed_utterance`)
```
rate = 1.3, min_coverage = 0.75, partials_n_frames = 160 (1.6 s)
wav_slices, mel_slices = compute_partial_slices(len(wav), rate, min_coverage)
pad wav with zeros up to wav_slices[-1].stop if needed
mel = wav_to_mel_spectrogram(wav)
mels = stack([mel[s] for s in mel_slices])          # (n_partials, 160, 40)
partial_embeds = model(mels)                         # (n_partials, 256)  via ONNX
raw_embed = mean(partial_embeds, axis=0)
embed = raw_embed / ||raw_embed||_2                  # final 256-d UPLOAD vector
```
`compute_partial_slices` is pure index arithmetic (resemblyzer `voice_encoder.py`)
— port it directly. Run each 160-frame partial through the ONNX model (batch=1),
average, L2-normalize, and that is the vector to upload.

---

## Reproducing / regenerating the model

The model is a reproducible build artifact (gitignored; only the script is
committed). Inside the bio Docker image (which has resemblyzer + torch):

```bash
docker run --rm \
  -v "$PWD/scripts:/scripts:ro" -v /tmp/voice_out:/out \
  --entrypoint bash <bio-image> -c \
  "pip install -q onnx onnxruntime && python /scripts/export_resemblyzer_onnx.py --out /out"
# end-to-end parity vs embed_utterance on a real clip:
#   python /scripts/export_resemblyzer_onnx.py --out /out --wav /out/sample.wav
```
The script fails (exit 1) if torch↔ONNX cosine parity drops below 0.999, so a
broken export can never ship. Take the printed sha256, rename to
`resemblyzer-<sha256>.onnx`, host it, and wire the web-app constants.

---

## Honesty / completeness — what is verified vs scaffold

**Fully working + verified (evidence):**
- The two bio endpoints `/voice/verify-embedding` + `/voice/enroll-embedding`
  reuse the exact downstream compare/store logic; covered by unit tests in
  `tests/unit/api/test_voice_routes.py` (the embedding verify path is asserted to
  reach an IDENTICAL verdict to the audio path for the same probe + centroid).
- The ONNX export is byte-faithful to the production torch model: torch↔ONNX
  cosine = 1.0 on random mel batches AND end-to-end vs `embed_utterance`.

**Scaffold / NOT yet verified (do not trust until done):**
- The **browser preprocessing port** (Steps 1b + 2). Measured sensitivity: with
  the synthesized reference clip, skipping the WebRTC VAD trim (the realistic
  "JS without a webrtcvad WASM build" shortcut) gives same-clip cosine **≈0.89**
  vs the full server preprocessing — still far above an impostor (**≈0.40**), but
  the enrolled template was computed server-side WITH the VAD, and the accept
  threshold is **0.65**. A ~0.11 cross-preprocessing gap on clean audio will be
  larger on noisy real-world audio and risks false-rejects near the threshold.
  Therefore the client mel + VAD MUST be validated to parity (Step 1b option 1)
  before `VITE_CLIENT_SIDE_VOICE_EMBEDDING` is enabled in any real flow.

**Exact steps remaining to canary the end-to-end client path:**
1. Build/obtain a WASM webrtcvad (mode 3, 30 ms, 16 kHz) and a librosa-parity
   Slaney mel STFT in JS; validate both against the Python reference on a corpus
   of real clips (target: same-speaker client-vs-server cosine ≥ ~0.95).
2. Host `resemblyzer-<sha256>.onnx` at `app.fivucsas.com/models/`, set the
   web-app constants, add the `manifest.json` entry (only after hosting).
3. Flip the Identity Core flag `app.auth.client-side-voice-embedding` ON FIRST
   (identity→web ordering, same caveat as facenet), then
   `VITE_CLIENT_SIDE_VOICE_EMBEDDING`, canary one tenant, compare verify
   accept-rates client-vs-server before broadening.
