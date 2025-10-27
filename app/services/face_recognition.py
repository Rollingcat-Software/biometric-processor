import json
import logging
import os
from typing import Tuple, Optional

import numpy as np
from PIL import Image
from deepface import DeepFace

from app.core.config import settings

logger = logging.getLogger(__name__)


class FaceRecognitionService:

    def __init__(self):
        logger.info("Initializing FaceRecognitionService...")
        logger.info(f"Model: {settings.FACE_RECOGNITION_MODEL}")
        logger.info(f"Detection backend: {settings.FACE_DETECTION_BACKEND}")

        # Warm up the model by loading it once
        try:
            DeepFace.build_model(settings.FACE_RECOGNITION_MODEL)
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading model: {e}")

    def extract_embedding(self, image_path: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Extract face embedding from image
        Returns: (success, embedding_json, error_message)
        """
        try:
            logger.info(f"Extracting embedding from: {image_path}")

            # Verify image exists and is valid
            if not os.path.exists(image_path):
                return False, None, "Image file not found"

            # Check if face exists in image
            try:
                face_objs = DeepFace.extract_faces(
                    img_path=image_path,
                    detector_backend=settings.FACE_DETECTION_BACKEND,
                    enforce_detection=True
                )

                if not face_objs or len(face_objs) == 0:
                    return False, None, "No face detected in image"

                if len(face_objs) > 1:
                    logger.warning(f"Multiple faces detected ({len(face_objs)}), using the first one")

            except Exception as e:
                logger.error(f"Face detection error: {e}")
                return False, None, f"Face detection failed: {str(e)}"

            # Extract embedding using represent
            embedding_objs = DeepFace.represent(
                img_path=image_path,
                model_name=settings.FACE_RECOGNITION_MODEL,
                detector_backend=settings.FACE_DETECTION_BACKEND,
                enforce_detection=True
            )

            if not embedding_objs or len(embedding_objs) == 0:
                return False, None, "Failed to extract face embedding"

            # Get the first face's embedding
            embedding = embedding_objs[0]["embedding"]

            # Convert to JSON string
            embedding_json = json.dumps(embedding)

            logger.info(f"Successfully extracted embedding (dimension: {len(embedding)})")
            return True, embedding_json, None

        except Exception as e:
            logger.error(f"Error extracting embedding: {e}")
            return False, None, f"Embedding extraction failed: {str(e)}"

    def verify_faces(self, image_path: str, stored_embedding_json: str) -> Tuple[bool, float, str]:
        """
        Verify if the face in image matches the stored embedding
        Returns: (verified, confidence, message)
        """
        try:
            logger.info(f"Verifying face from: {image_path}")

            # Extract embedding from new image
            success, new_embedding_json, error = self.extract_embedding(image_path)
            if not success:
                return False, 0.0, error or "Failed to extract face from image"

            # Parse embeddings
            stored_embedding = np.array(json.loads(stored_embedding_json))
            new_embedding = np.array(json.loads(new_embedding_json))

            # Calculate cosine similarity
            distance = self._calculate_cosine_distance(stored_embedding, new_embedding)

            # Convert distance to confidence (0-1 scale)
            # Cosine distance: 0 = identical, 1 = completely different
            confidence = 1.0 - distance

            # Verify against threshold
            verified = distance < settings.VERIFICATION_THRESHOLD

            message = "Face verified successfully" if verified else "Face does not match"

            logger.info(
                f"Verification result: verified={verified}, distance={distance:.4f}, confidence={confidence:.4f}")

            return verified, confidence, message

        except Exception as e:
            logger.error(f"Error verifying faces: {e}")
            return False, 0.0, f"Verification failed: {str(e)}"

    def _calculate_cosine_distance(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Calculate cosine distance between two embeddings"""
        # Normalize embeddings
        emb1_norm = emb1 / np.linalg.norm(emb1)
        emb2_norm = emb2 / np.linalg.norm(emb2)

        # Calculate cosine similarity
        similarity = np.dot(emb1_norm, emb2_norm)

        # Convert to distance (0 = identical, 1 = opposite)
        distance = 1.0 - similarity

        return float(distance)

    def validate_image(self, image_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate if image is suitable for face recognition
        Returns: (is_valid, error_message)
        """
        try:
            # Check file exists
            if not os.path.exists(image_path):
                return False, "Image file does not exist"

            # Check file size
            file_size = os.path.getsize(image_path)
            if file_size > settings.MAX_FILE_SIZE:
                return False, f"Image too large (max {settings.MAX_FILE_SIZE} bytes)"

            if file_size == 0:
                return False, "Image file is empty"

            # Try to open image
            try:
                img = Image.open(image_path)
                img.verify()

                # Check image dimensions
                img = Image.open(image_path)  # Reopen after verify
                width, height = img.size

                if width < 100 or height < 100:
                    return False, "Image resolution too low (minimum 100x100)"

            except Exception as e:
                return False, f"Invalid image file: {str(e)}"

            return True, None

        except Exception as e:
            logger.error(f"Error validating image: {e}")
            return False, f"Validation error: {str(e)}"


# Singleton instance
face_recognition_service = FaceRecognitionService()
