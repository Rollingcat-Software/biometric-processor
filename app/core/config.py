import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "FIVUCSAS Biometric Processor"
    VERSION: str = "1.0.0-MVP"

    # File upload settings
    UPLOAD_FOLDER: str = "./temp_uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB

    # Face recognition settings
    FACE_DETECTION_BACKEND: str = "opencv"  # opencv, ssd, dlib, mtcnn, retinaface
    FACE_RECOGNITION_MODEL: str = "VGG-Face"  # VGG-Face, Facenet, OpenFace, DeepFace, DeepID, ArcFace
    DISTANCE_METRIC: str = "cosine"  # cosine, euclidean, euclidean_l2

    # Verification threshold
    VERIFICATION_THRESHOLD: float = 0.40  # For VGG-Face with cosine distance

    class Config:
        env_file = ".env"


settings = Settings()

# Create upload folder if it doesn't exist
os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
