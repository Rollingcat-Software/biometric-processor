# app/core/card_type_model/detector.py
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
from ultralytics import YOLO


class CardDetectionResult:
    def __init__(
        self,
        detected: bool,
        class_name: Optional[str] = None,
        class_id: Optional[int] = None,
        confidence: Optional[float] = None,
    ):
        self.detected = detected
        self.class_name = class_name
        self.class_id = class_id
        self.confidence = confidence


@lru_cache
def get_yolo_model() -> YOLO:
    """YOLO modelini bir kez yükleyip cache'ler."""
    model_path = Path(__file__).with_name("best.pt")
    return YOLO(model_path.as_posix())


def detect_card_type(image: np.ndarray, conf_threshold: float = 0.5) -> CardDetectionResult:
    """
    image: RGB (H, W, 3) numpy array
    """
    model = get_yolo_model()
    results = model(image, conf=conf_threshold, verbose=False)
    result = results[0]

    if len(result.boxes) == 0:
        return CardDetectionResult(detected=False)

    best_box = max(result.boxes, key=lambda b: float(b.conf[0]))
    cls_id = int(best_box.cls[0])
    conf = float(best_box.conf[0])
    cls_name = model.names[cls_id]

    return CardDetectionResult(
        detected=True,
        class_name=cls_name,
        class_id=cls_id,
        confidence=conf,
    )


