import logging
import os
import uuid

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.core.config import settings
from app.models.schemas import FaceEnrollResponse, FaceVerificationResponse
from app.services.face_recognition import face_recognition_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/face/enroll", response_model=FaceEnrollResponse)
async def enroll_face(file: UploadFile = File(...)):
    """
    Enroll a user's face by extracting and returning the embedding
    """
    temp_file_path = None

    try:
        logger.info(f"Face enrollment request received: {file.filename}")

        # Validate file type
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Save uploaded file temporarily
        file_extension = os.path.splitext(file.filename)[1]
        temp_filename = f"{uuid.uuid4()}{file_extension}"
        temp_file_path = os.path.join(settings.UPLOAD_FOLDER, temp_filename)

        with open(temp_file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        logger.info(f"File saved temporarily: {temp_file_path}")

        # Validate image
        is_valid, error_msg = face_recognition_service.validate_image(temp_file_path)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # Extract face embedding
        success, embedding_json, error = face_recognition_service.extract_embedding(temp_file_path)

        if not success:
            raise HTTPException(status_code=400, detail=error or "Failed to extract face embedding")

        logger.info("Face enrolled successfully")

        return FaceEnrollResponse(
            success=True,
            message="Face enrolled successfully",
            embedding=embedding_json,
            face_confidence=1.0
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enrollment error: {e}")
        raise HTTPException(status_code=500, detail=f"Enrollment failed: {str(e)}")
    finally:
        # Cleanup temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Temporary file deleted: {temp_file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {e}")


@router.post("/face/verify", response_model=FaceVerificationResponse)
async def verify_face(
        file: UploadFile = File(...),
        stored_embedding: str = Form(...)
):
    """
    Verify a face against stored embedding
    """
    temp_file_path = None

    try:
        logger.info(f"Face verification request received: {file.filename}")

        # Validate file type
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Save uploaded file temporarily
        file_extension = os.path.splitext(file.filename)[1]
        temp_filename = f"{uuid.uuid4()}{file_extension}"
        temp_file_path = os.path.join(settings.UPLOAD_FOLDER, temp_filename)

        with open(temp_file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        logger.info(f"File saved temporarily: {temp_file_path}")

        # Validate image
        is_valid, error_msg = face_recognition_service.validate_image(temp_file_path)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # Verify face
        verified, confidence, message = face_recognition_service.verify_faces(
            temp_file_path,
            stored_embedding
        )

        logger.info(f"Verification complete: verified={verified}, confidence={confidence:.4f}")

        return FaceVerificationResponse(
            verified=verified,
            confidence=confidence,
            message=message,
            distance=1.0 - confidence
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verification error: {e}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")
    finally:
        # Cleanup temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Temporary file deleted: {temp_file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {e}")


@router.get("/face/health")
def face_health_check():
    """Health check for face recognition service"""
    return {
        "status": "healthy",
        "model": settings.FACE_RECOGNITION_MODEL,
        "detector": settings.FACE_DETECTION_BACKEND
    }
