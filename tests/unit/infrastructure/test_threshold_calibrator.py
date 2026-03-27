import json

from app.infrastructure.ml.liveness.threshold_calibrator import ThresholdCalibrator


def test_load_scores_reads_real_and_spoof_entries(tmp_path):
    log_path = tmp_path / "liveness.jsonl"
    rows = [
        {"label": "real", "score": 88.0},
        {"label": "spoof", "score": 22.0},
        {"label": "live", "liveness_score": 91.0},
        {"label": "attack", "score": 10.0},
        {"label": "unknown", "score": 50.0},
    ]
    log_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    calibrator = ThresholdCalibrator(log_path)
    real_scores, spoof_scores = calibrator.load_scores()

    assert real_scores == [88.0, 91.0]
    assert spoof_scores == [22.0, 10.0]


def test_find_optimal_threshold_target_far_prefers_low_frr():
    calibrator = ThresholdCalibrator("ignored.jsonl")

    result = calibrator.find_optimal_threshold(
        real_scores=[78.0, 82.0, 88.0, 91.0],
        spoof_scores=[12.0, 24.0, 35.0, 44.0],
        target_far=0.0,
        strategy="target_far",
    )

    assert result.optimal_threshold == 78.0
    assert result.far == 0.0
    assert result.frr == 0.0
    assert result.sample_count == 8


def test_find_optimal_threshold_eer_returns_balanced_threshold():
    calibrator = ThresholdCalibrator("ignored.jsonl")

    result = calibrator.find_optimal_threshold(
        real_scores=[60.0, 65.0, 70.0, 75.0],
        spoof_scores=[40.0, 45.0, 50.0, 55.0],
        strategy="eer",
    )

    assert 55.0 <= result.optimal_threshold <= 60.0
    assert 0.0 <= result.eer <= 0.5


def test_write_env_threshold_updates_existing_key(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("DEBUG=true\nLIVENESS_THRESHOLD=70.0\n", encoding="utf-8")

    calibrator = ThresholdCalibrator("ignored.jsonl")
    calibrator.write_env_threshold(env_path=env_path, threshold=83.25)

    content = env_path.read_text(encoding="utf-8")
    assert "LIVENESS_THRESHOLD=83.25" in content
    assert content.count("LIVENESS_THRESHOLD=") == 1
