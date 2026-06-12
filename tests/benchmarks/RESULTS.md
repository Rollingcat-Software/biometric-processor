# Face-Recognition Benchmark — methodology & results (template)

Reproducible 1:1 verification accuracy for the **production face model**
(FaceNet-512 via DeepFace, cosine distance, accept threshold 0.45 — the same model
and operating point used by `/verify`). This file + harness exist so that the
face-accuracy numbers used on the poster / in the defense can be **re-derived from a
committed script and raw CSV**, instead of living only on a slide.

Harness: [`face_recognition_accuracy.py`](./face_recognition_accuracy.py).

> **Status: results NOT yet committed.** The table below is a template. Fill it in
> **only** from a CSV produced by the harness on this machine — do not transcribe
> numbers from slides. Until the CSVs land, this repo makes **no** verified
> face-accuracy claim.

## Results (fill from your run)

| Dataset    | Pairs | AUC | EER | FAR @ 0.45 | TAR | CSV |
|------------|------:|:---:|:---:|:----------:|:---:|-----|
| LFW        |       |     |     |            |     | `lfw_results.csv` |
| CFP-FP     |       |     |     |            |     | `cfp_fp_results.csv` |
| AgeDB-30   |       |     |     |            |     | `agedb30_results.csv` |

Model: FaceNet-512 (512-D), cosine distance, threshold 0.45.

**Targets to confirm** (these are the values currently *claimed on the poster* — re-run
to verify and replace the table above with your measured figures): LFW ≈ 0.9943 AUC /
EER 1.93 % / FAR 0.27 % / TAR 95.6 %; CFP-FP ≈ 0.9845 AUC; AgeDB-30 ≈ 0.9475 AUC; over
≈12,062 pairs (≈1,342 images / 100 identities). A prior internal note also recorded
AgeDB-30 ≈ 0.9475 (`archive/2026-04-pre-roadmap-2028/BIOMETRIC_PIPELINE_AUDIT_2026-04-28.md`);
methodology in `docs/01-getting-started/METRICS_COLLECTION_GUIDE.md`.

## Reproduce

```bash
# Convert the official LFW pairs.txt to "imgA imgB label" lines first, then:
python tests/benchmarks/face_recognition_accuracy.py \
    --pairs lfw_pairs.txt --images ~/datasets/lfw \
    --model Facenet512 --threshold 0.45 --out lfw_results.csv
# repeat for CFP-FP and AgeDB-30
```

The script embeds each image (DeepFace, FaceNet-512, MTCNN), computes cosine distance
per pair, and reports **AUC** (`roc_auc_score`), **EER**, and **TAR/FAR** at the
threshold, writing a per-pair CSV.

## To finish (turns this template into evidence)

1. Run the harness on LFW / CFP-FP / AgeDB-30 (or commit the eval notebook that produced the numbers).
2. Commit the raw per-pair CSVs next to this file.
3. Fill the results table from those CSVs.

Once (1)–(3) land, the poster's face-accuracy numbers have a one-click, defensible source.
