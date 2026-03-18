"""WebSocket frame handler for proctoring."""

import base64
import logging
import struct
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FrameResult:
    """Result of frame processing."""

    session_id: UUID
    frame_number: int
    risk_score: float
    face_detected: bool
    face_matched: bool
    incidents_created: int
    processing_time_ms: float
    analysis: Dict[str, Any]
    rate_limit: Optional[Dict[str, Any]] = None


@dataclass
class BinaryFrameHeader:
    """Header for binary frame protocol."""

    version: int  # 1 byte
    frame_type: int  # 1 byte (0=image, 1=audio, 2=combined)
    flags: int  # 2 bytes
    session_id: UUID  # 16 bytes
    frame_number: int  # 4 bytes
    timestamp: int  # 8 bytes (unix ms)
    payload_size: int  # 4 bytes

    HEADER_SIZE = 36  # Total header size in bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> "BinaryFrameHeader":
        """Parse header from binary data."""
        if len(data) < cls.HEADER_SIZE:
            raise ValueError(f"Header too small: {len(data)} < {cls.HEADER_SIZE}")

        # Unpack header fields
        version, frame_type = struct.unpack("!BB", data[0:2])
        flags = struct.unpack("!H", data[2:4])[0]
        session_bytes = data[4:20]
        frame_number = struct.unpack("!I", data[20:24])[0]
        timestamp = struct.unpack("!Q", data[24:32])[0]
        payload_size = struct.unpack("!I", data[32:36])[0]

        # Convert session bytes to UUID
        session_id = UUID(bytes=session_bytes)

        return cls(
            version=version,
            frame_type=frame_type,
            flags=flags,
            session_id=session_id,
            frame_number=frame_number,
            timestamp=timestamp,
            payload_size=payload_size,
        )

    def to_bytes(self) -> bytes:
        """Serialize header to bytes."""
        return (
            struct.pack("!BB", self.version, self.frame_type)
            + struct.pack("!H", self.flags)
            + self.session_id.bytes
            + struct.pack("!I", self.frame_number)
            + struct.pack("!Q", self.timestamp)
            + struct.pack("!I", self.payload_size)
        )


class WebSocketFrameHandler:
    """Handle incoming WebSocket frames for proctoring.

    Supports:
    - Binary frame protocol for efficient image transfer
    - JSON messages for configuration and control
    - Frame rate limiting
    """

    def __init__(
        self,
        submit_frame_use_case,
        max_frame_size: int = 5_000_000,  # 5MB
    ):
        self._submit_frame_use_case = submit_frame_use_case
        self._max_frame_size = max_frame_size

    async def handle_binary_frame(
        self,
        data: bytes,
        session_id: UUID,
        tenant_id: str,
    ) -> FrameResult:
        """Handle binary frame data.

        Supports two formats:
        1. Raw JPEG/PNG image bytes
        2. Binary protocol with header

        Args:
            data: Binary frame data
            session_id: Session identifier
            tenant_id: Tenant identifier

        Returns:
            Frame processing result
        """
        start_time = time.perf_counter()

        # Check size limit
        if len(data) > self._max_frame_size:
            raise ValueError(f"Frame too large: {len(data)} > {self._max_frame_size}")

        # Detect format and extract image
        image, frame_number, audio_data = self._parse_binary_data(data, session_id)

        if image is None:
            raise ValueError("Failed to decode image from binary data")

        # Process frame using use case
        from app.application.use_cases.proctor.submit_frame import (
            SubmitFrameRequest as UseCaseRequest,
        )

        result = await self._submit_frame_use_case.execute(
            UseCaseRequest(
                session_id=session_id,
                tenant_id=tenant_id,
                frame=image,
                frame_number=frame_number,
                audio_data=audio_data,
            )
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        return FrameResult(
            session_id=session_id,
            frame_number=result.frame_number,
            risk_score=result.risk_score,
            face_detected=result.face_detected,
            face_matched=result.face_matched,
            incidents_created=result.incidents_created,
            processing_time_ms=processing_time,
            analysis=result.analysis,
            rate_limit=result.rate_limit,
        )

    async def handle_json_message(
        self,
        message: dict,
        session_id: UUID,
        tenant_id: str,
    ) -> dict:
        """Handle JSON message from WebSocket.

        Supported message types:
        - ping: Heartbeat
        - config: Update session config
        - frame: Base64-encoded frame

        Args:
            message: Parsed JSON message
            session_id: Session identifier
            tenant_id: Tenant identifier

        Returns:
            Response message
        """
        msg_type = message.get("type")

        if msg_type == "ping":
            return {
                "type": "pong",
                "timestamp": int(time.time() * 1000),
            }

        elif msg_type == "frame":
            # Handle base64-encoded frame
            frame_b64 = message.get("payload", {}).get("frame_base64")
            if not frame_b64:
                raise ValueError("Missing frame_base64 in payload")

            try:
                frame_bytes = base64.b64decode(frame_b64)
            except Exception as e:
                raise ValueError(f"Invalid base64 frame data: {e}")
            message.get("payload", {}).get("frame_number", 0)

            result = await self.handle_binary_frame(
                frame_bytes,
                session_id,
                tenant_id,
            )

            return {
                "type": "result",
                "session_id": str(session_id),
                "payload": {
                    "frame_number": result.frame_number,
                    "risk_score": result.risk_score,
                    "face_detected": result.face_detected,
                    "face_matched": result.face_matched,
                    "incidents_created": result.incidents_created,
                    "processing_time_ms": result.processing_time_ms,
                    "analysis": result.analysis,
                },
            }

        elif msg_type == "config":
            # Configuration update (future use)
            return {
                "type": "config_ack",
                "status": "ok",
            }

        else:
            raise ValueError(f"Unknown message type: {msg_type}")

    def _parse_binary_data(
        self,
        data: bytes,
        default_session_id: UUID,
    ) -> Tuple[Optional[np.ndarray], int, Optional[np.ndarray]]:
        """Parse binary data to extract image and optional audio.

        Args:
            data: Raw binary data
            default_session_id: Session ID if not in header

        Returns:
            Tuple of (image, frame_number, audio_data)
        """
        # Check if data starts with our protocol header
        if len(data) >= BinaryFrameHeader.HEADER_SIZE:
            try:
                # Try to parse as binary protocol
                if data[0] == 1:  # Protocol version 1
                    header = BinaryFrameHeader.from_bytes(data)
                    payload = data[BinaryFrameHeader.HEADER_SIZE:]

                    if header.frame_type == 0:  # Image only
                        image = self._decode_image(payload)
                        return image, header.frame_number, None

                    elif header.frame_type == 2:  # Combined
                        # First 4 bytes of payload is image size
                        img_size = struct.unpack("!I", payload[:4])[0]
                        img_data = payload[4 : 4 + img_size]
                        audio_data = payload[4 + img_size :]

                        image = self._decode_image(img_data)
                        audio = np.frombuffer(audio_data, dtype=np.float32)
                        return image, header.frame_number, audio

            except Exception as e:
                logger.debug(f"Binary protocol parse failed, trying raw image: {e}")

        # Fall back to raw image decoding
        image = self._decode_image(data)
        return image, 0, None

    def _decode_image(self, data: bytes) -> Optional[np.ndarray]:
        """Decode image bytes to numpy array.

        Args:
            data: Image bytes (JPEG, PNG, or WebP)

        Returns:
            Decoded image as BGR numpy array, or None if failed
        """
        try:
            nparr = np.frombuffer(data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return image
        except Exception as e:
            logger.error(f"Image decode failed: {e}")
            return None

    def validate_image(self, image: np.ndarray) -> bool:
        """Validate decoded image meets requirements.

        Args:
            image: Decoded image array

        Returns:
            True if valid, False otherwise
        """
        if image is None:
            return False

        # Check dimensions
        h, w = image.shape[:2]
        if h < 100 or w < 100:
            logger.warning(f"Image too small: {w}x{h}")
            return False

        if h > 4096 or w > 4096:
            logger.warning(f"Image too large: {w}x{h}")
            return False

        # Check channels
        if len(image.shape) != 3 or image.shape[2] != 3:
            logger.warning(f"Invalid image channels: {image.shape}")
            return False

        return True
