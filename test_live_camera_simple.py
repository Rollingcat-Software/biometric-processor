#!/usr/bin/env python3
"""
Simple Live Camera Test Client - Like C++ + OpenCV Version
Opens a camera window and processes frames in real-time via WebSocket.

Usage:
    python test_live_camera_simple.py

    Press 'q' to quit
    Press 's' to take a screenshot
    Press 'f' to toggle FPS display
"""

import asyncio
import base64
import cv2
import json
import numpy as np
import websockets
from datetime import datetime
from typing import Optional
import argparse


class LiveCameraClient:
    """Simple live camera client with OpenCV window."""

    def __init__(self, ws_url: str, camera_id: int = 0, mode: str = "quality_only"):
        self.ws_url = ws_url
        self.camera_id = camera_id
        self.mode = mode
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False

        # Statistics
        self.frame_count = 0
        self.processed_count = 0
        self.fps = 0.0
        self.last_result = None

        # Display settings
        self.show_fps = True
        self.window_name = "Biometric Live Analysis"

    async def connect(self):
        """Connect to WebSocket server."""
        print(f"Connecting to {self.ws_url}...")
        self.websocket = await websockets.connect(self.ws_url)
        print("✓ Connected to WebSocket server")

        # Send configuration
        config = {
            "type": "config",
            "data": {
                "mode": self.mode,
                "frame_skip": 0,  # Process all frames
                "quality_threshold": 70.0,
                "user_id": None,
                "tenant_id": "test-client"
            }
        }

        await self.websocket.send(json.dumps(config))

        # Wait for config acknowledgment
        response = await self.websocket.recv()
        response_data = json.loads(response)

        if response_data.get("type") == "config_ack":
            print(f"✓ Configuration acknowledged: {response_data['data']}")
        else:
            print(f"⚠ Unexpected response: {response_data}")

    async def send_frame(self, frame: np.ndarray):
        """Send a frame to the server."""
        if not self.websocket:
            return

        # Encode frame as JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

        # Convert to base64
        frame_base64 = base64.b64encode(buffer).decode('utf-8')

        # Send to server
        message = {
            "type": "frame",
            "data": frame_base64
        }

        await self.websocket.send(json.dumps(message))
        self.frame_count += 1

    async def receive_result(self):
        """Receive analysis result from server."""
        if not self.websocket:
            return None

        try:
            response = await asyncio.wait_for(self.websocket.recv(), timeout=0.1)
            response_data = json.loads(response)

            if response_data.get("type") == "result":
                self.processed_count += 1
                self.last_result = response_data["data"]
                return self.last_result
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            print(f"Error receiving result: {e}")

        return None

    def draw_overlay(self, frame: np.ndarray):
        """Draw analysis results on frame."""
        height, width = frame.shape[:2]

        # Draw semi-transparent overlay at top
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (width, 120), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

        # Draw FPS
        if self.show_fps:
            cv2.putText(
                frame, f"FPS: {self.fps:.1f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
            )

        # Draw frame counter
        cv2.putText(
            frame, f"Frames: {self.frame_count} | Processed: {self.processed_count}",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
        )

        # Draw analysis results if available
        if self.last_result:
            y_offset = 90

            # Quality score
            if self.last_result.get("quality"):
                quality = self.last_result["quality"]
                score = quality.get("score", 0)
                passed = quality.get("passed", False)

                color = (0, 255, 0) if passed else (0, 0, 255)
                text = f"Quality: {score:.1f}% {'✓' if passed else '✗'}"
                cv2.putText(
                    frame, text, (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
                )

            # Draw face bounding box
            if self.last_result.get("face"):
                face = self.last_result["face"]
                x = int(face.get("x", 0))
                y = int(face.get("y", 0))
                w = int(face.get("width", 0))
                h = int(face.get("height", 0))
                confidence = face.get("confidence", 0)

                # Draw rectangle
                color = (0, 255, 0) if confidence > 0.9 else (0, 255, 255)
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

                # Draw confidence
                cv2.putText(
                    frame, f"{confidence:.2f}", (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
                )

            # Liveness result
            if self.last_result.get("liveness"):
                liveness = self.last_result["liveness"]
                is_live = liveness.get("is_live", False)
                confidence = liveness.get("confidence", 0)

                color = (0, 255, 0) if is_live else (0, 0, 255)
                text = f"Liveness: {'LIVE' if is_live else 'SPOOF'} ({confidence:.2f})"
                cv2.putText(
                    frame, text, (width - 300, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
                )

            # Demographics
            if self.last_result.get("demographics"):
                demo = self.last_result["demographics"]
                age = demo.get("age", 0)
                gender = demo.get("gender", "unknown")
                emotion = demo.get("dominant_emotion", "unknown")

                text = f"Age: {age} | {gender.title()} | {emotion.title()}"
                cv2.putText(
                    frame, text, (width - 400, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2
                )

            # Enrollment ready
            if self.last_result.get("enrollment_ready"):
                ready = self.last_result["enrollment_ready"]
                is_ready = ready.get("ready", False)

                if is_ready:
                    cv2.putText(
                        frame, "READY TO ENROLL", (width // 2 - 150, height - 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3
                    )

        return frame

    async def run(self):
        """Run the live camera client."""
        # Open camera
        print(f"Opening camera {self.camera_id}...")
        cap = cv2.VideoCapture(self.camera_id)

        if not cap.isOpened():
            print(f"✗ Failed to open camera {self.camera_id}")
            return

        # Set camera properties
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 30)

        print("✓ Camera opened successfully")

        # Connect to WebSocket
        await self.connect()

        # Create window
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, 1280, 720)

        print("\n" + "=" * 60)
        print("LIVE CAMERA ANALYSIS STARTED")
        print("=" * 60)
        print("Press 'q' to quit")
        print("Press 's' to take a screenshot")
        print("Press 'f' to toggle FPS display")
        print("=" * 60 + "\n")

        self.running = True
        last_time = cv2.getTickCount()

        try:
            while self.running:
                # Read frame from camera
                ret, frame = cap.read()
                if not ret:
                    print("✗ Failed to read frame from camera")
                    break

                # Calculate FPS
                current_time = cv2.getTickCount()
                time_diff = (current_time - last_time) / cv2.getTickFrequency()
                if time_diff > 0:
                    self.fps = 1.0 / time_diff
                last_time = current_time

                # Send frame to server
                await self.send_frame(frame)

                # Receive result (non-blocking)
                await self.receive_result()

                # Draw overlay
                frame = self.draw_overlay(frame)

                # Show frame
                cv2.imshow(self.window_name, frame)

                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF

                if key == ord('q'):
                    print("\nQuitting...")
                    break
                elif key == ord('s'):
                    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    cv2.imwrite(filename, frame)
                    print(f"Screenshot saved: {filename}")
                elif key == ord('f'):
                    self.show_fps = not self.show_fps
                    print(f"FPS display: {'ON' if self.show_fps else 'OFF'}")

        finally:
            # Cleanup
            print("\nCleaning up...")
            self.running = False
            cap.release()
            cv2.destroyAllWindows()

            if self.websocket:
                await self.websocket.close()

            print(f"\n✓ Session complete:")
            print(f"  - Total frames sent: {self.frame_count}")
            print(f"  - Frames processed: {self.processed_count}")
            print(f"  - Average FPS: {self.fps:.1f}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Live Camera Test Client")
    parser.add_argument(
        "--url",
        default="ws://localhost:8001/api/v1/ws/live-analysis",
        help="WebSocket URL (default: ws://localhost:8001/api/v1/ws/live-analysis)"
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Camera device ID (default: 0)"
    )
    parser.add_argument(
        "--mode",
        choices=["quality_only", "liveness", "demographics", "enrollment_ready", "full"],
        default="quality_only",
        help="Analysis mode (default: quality_only)"
    )

    args = parser.parse_args()

    client = LiveCameraClient(
        ws_url=args.url,
        camera_id=args.camera,
        mode=args.mode
    )

    try:
        await client.run()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
