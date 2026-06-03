# Face-Recognition Benchmark — methodology & results

Reproducible 1:1 verification accuracy for the **production face model**
(FaceNet-512 via DeepFace, cosine distance, accept threshold 0.45 — the same model
and operating point used by `/verify`). This file exists so every face-accuracy
number on the poster / in the defense is backed by a **committed, re-runnable
script + a raw per-pair CSV**, not a slide.

Harness: [`face_recognition_accuracy.py`](./face_recognition_accuracy.py).

## Reported results

> **Provenance:** produced by **Ayşenur Arıcı's** offline evaluation of FaceNet-512
> on the standard public verification protocols below. These are *model-accuracy*
> benchmarks (offline, on the public datasets) — **not** end-to-end production-API
> latency, which is tracked separately. The raw per-pair CSVs are **pending commit**
> (see "To finish" below); until they land, treat the table as *reported, not yet
> independently re-derived in this repo*.

| Dataset    | Pairs  | AUC    | EER    | FAR @ 0.45 | TAR    |
|------------|-------:|:------:|:------:|:----------:|:------:|
| LFW        | 5,600  | 0.9943 | 1.93 % | 0.27 %     | 95.6 % |
| CFP-FP     | 1,378  | 0.9845 | —      | —          | —      |
| AgeDB-30   | —      | 0.9475 | —      | —          | —      |
| **Total**  | 12,062 |        |        |            |        |

Scale: 1,342 enrolled images across 100 identities; 12,062 verification pairs over
the three protocols. Model: **FaceNet-512** (512-D), cosine distance, threshold 0.45.

Cross-check (independent corroboration of provenance): AgeDB-30 ≈ 0.9475 was already
recorded in `archive/2026-04-pre-roadmap-2028/BIOMETRIC_PIPELINE_AUDIT_2026-04-28.md`,
and the methodology is documented in `docs/01-getting-started/METRICS_COLLECTION_GUIDE.md`.

## Reproduce

```bash
# LFW (convert the official pairs.txt to "imgA imgB label" lines first)
python tests/benchmarks/face_recognition_accuracy.py \
    --pairs lfw_pairs.txt --images ~/datasets/lfw \
    --model Facenet512 --threshold 0.45 --out lfw_results.csv
# repeat with --pairs cfp_fp_pairs.txt / agedb30_pairs.txt
```

The script embeds each image with DeepFace (FaceNet-512, MTCNN detector), computes
cosine distance per pair, then reports **AUC** (`roc_auc_score`), **EER**, and
**TAR/FAR** at the threshold, and writes a per-pair CSV.

## To finish (turns "reported" into "reproducible")

1. Commit Ayşenur's eval artifact (notebook or script) that produced the table.
2. Commit the raw per-pair CSVs here: `lfw_results.csv`, `cfp_fp_results.csv`,
   `agedb30_results.csv` (the script's `--out`).
3. Fill the empty CFP-FP / AgeDB-30 cells from those CSVs.

Once (1)–(3) land, the poster's "99.43 % AUC" has a one-click source for the jury.
