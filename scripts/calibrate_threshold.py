"""Calibrate liveness threshold from labeled JSONL logs.

Usage:
    python scripts/calibrate_threshold.py --logs logs/liveness.jsonl
    python scripts/calibrate_threshold.py --logs logs/liveness.jsonl --strategy eer
    python scripts/calibrate_threshold.py --logs logs/liveness.jsonl --write-env .env
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.infrastructure.ml.liveness.threshold_calibrator import ThresholdCalibrator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calibrate liveness threshold from labeled JSONL score logs.",
    )
    parser.add_argument(
        "--logs",
        required=True,
        help="Path to JSONL file with labeled liveness scores",
    )
    parser.add_argument(
        "--target-far",
        type=float,
        default=0.01,
        help="Target false acceptance rate for threshold search",
    )
    parser.add_argument(
        "--strategy",
        choices=("target_far", "eer"),
        default="target_far",
        help="Optimization strategy",
    )
    parser.add_argument(
        "--write-env",
        help="Optional .env file to update with calibrated LIVENESS_THRESHOLD",
    )
    parser.add_argument(
        "--env-key",
        default="LIVENESS_THRESHOLD",
        help="Env key to update when --write-env is used",
    )
    parser.add_argument(
        "--output-json",
        action="store_true",
        help="Print machine-readable JSON only",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    calibrator = ThresholdCalibrator(args.logs)
    real_scores, spoof_scores = calibrator.load_scores()
    result = calibrator.find_optimal_threshold(
        real_scores=real_scores,
        spoof_scores=spoof_scores,
        target_far=args.target_far,
        strategy=args.strategy,
    )

    if args.write_env:
        calibrator.write_env_threshold(
            env_path=Path(args.write_env),
            threshold=result.optimal_threshold,
            key=args.env_key,
        )

    payload = result.to_dict()
    if args.write_env:
        payload["env_updated"] = str(Path(args.write_env))

    if args.output_json:
        print(json.dumps(payload, indent=2))
        return

    print(f"strategy={payload['strategy']}")
    print(f"optimal_threshold={payload['optimal_threshold']}")
    print(f"far={payload['far']}")
    print(f"frr={payload['frr']}")
    print(f"eer={payload['eer']}")
    print(f"sample_count={payload['sample_count']}")
    print(f"real_count={payload['real_count']}")
    print(f"spoof_count={payload['spoof_count']}")
    if args.write_env:
        print(f"env_updated={payload['env_updated']}")


if __name__ == "__main__":
    main()
