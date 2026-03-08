"""Model quantization utilities for faster inference.

Provides utilities for quantizing ML models to INT8 format for improved
inference performance. Supports TensorFlow/TFLite and ONNX models.

INT8 quantization benefits:
- 3-4x faster inference on CPU
- 2x faster inference on GPU (with TensorRT)
- 4x smaller model size
- Lower memory bandwidth requirements
"""

import os
import logging
from pathlib import Path
from typing import List, Optional, Callable, Iterator

import numpy as np

logger = logging.getLogger(__name__)


class ModelQuantizer:
    """Quantize TensorFlow and ONNX models to INT8 for faster inference.

    Supports two quantization approaches:
    1. Dynamic quantization: Weights quantized at conversion, activations at runtime
    2. Static quantization: Requires calibration data for optimal quantization

    Usage:
        quantizer = ModelQuantizer(Path("/models"))

        # Quantize TensorFlow model
        tflite_path = quantizer.quantize_tensorflow_model(
            "saved_model_dir",
            "facenet_int8",
            calibration_images
        )

        # Quantize ONNX model
        onnx_path = quantizer.quantize_onnx_model(
            "model.onnx",
            "facenet_int8",
            calibration_images
        )
    """

    def __init__(self, models_dir: Path):
        """Initialize quantizer.

        Args:
            models_dir: Directory to store quantized models
        """
        self.models_dir = models_dir
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def quantize_tensorflow_model(
        self,
        model_path: str,
        output_name: str,
        calibration_data: List[np.ndarray],
        input_shape: tuple = (1, 224, 224, 3),
        quantization_type: str = "int8",
    ) -> Path:
        """Quantize a TensorFlow SavedModel to INT8 TFLite.

        Uses post-training quantization with representative dataset
        for calibration to achieve optimal quantization accuracy.

        Args:
            model_path: Path to SavedModel directory or .h5 file
            output_name: Name for output file (without extension)
            calibration_data: List of numpy arrays for calibration
            input_shape: Model input shape (batch, height, width, channels)
            quantization_type: "int8" for full integer, "float16" for half precision

        Returns:
            Path to quantized TFLite model

        Raises:
            ImportError: If TensorFlow is not installed
            ValueError: If model cannot be loaded or converted
        """
        import tensorflow as tf

        logger.info(f"Quantizing TensorFlow model: {model_path}")

        # Load the model
        if model_path.endswith(".h5"):
            model = tf.keras.models.load_model(model_path)
            converter = tf.lite.TFLiteConverter.from_keras_model(model)
        else:
            converter = tf.lite.TFLiteConverter.from_saved_model(model_path)

        # Enable optimizations
        converter.optimizations = [tf.lite.Optimize.DEFAULT]

        if quantization_type == "int8":
            # Full integer quantization requires representative dataset
            def representative_dataset() -> Iterator[List[np.ndarray]]:
                for data in calibration_data[:100]:  # Use max 100 samples
                    sample = data.astype(np.float32)
                    if len(sample.shape) == 3:
                        sample = np.expand_dims(sample, axis=0)
                    yield [sample]

            converter.representative_dataset = representative_dataset

            # Full integer quantization
            converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
            converter.inference_input_type = tf.int8
            converter.inference_output_type = tf.int8

            suffix = "_int8"

        elif quantization_type == "float16":
            # Float16 quantization (smaller but less speedup)
            converter.target_spec.supported_types = [tf.float16]
            suffix = "_fp16"

        else:
            # Dynamic range quantization
            suffix = "_dynamic"

        # Convert
        try:
            quantized_model = converter.convert()
        except Exception as e:
            logger.error(f"TFLite conversion failed: {e}")
            raise ValueError(f"Failed to quantize model: {e}")

        # Save
        output_path = self.models_dir / f"{output_name}{suffix}.tflite"
        output_path.write_bytes(quantized_model)

        # Log size comparison
        original_size = self._get_model_size(model_path)
        quantized_size = len(quantized_model)

        logger.info(f"Quantized model saved to {output_path}")
        logger.info(f"Original size: {original_size / 1024 / 1024:.2f} MB")
        logger.info(f"Quantized size: {quantized_size / 1024 / 1024:.2f} MB")
        logger.info(f"Size reduction: {(1 - quantized_size/original_size)*100:.1f}%")

        return output_path

    def quantize_onnx_model(
        self,
        model_path: str,
        output_name: str,
        calibration_data: Optional[List[np.ndarray]] = None,
        quantization_type: str = "dynamic",
    ) -> Path:
        """Quantize an ONNX model to INT8.

        Supports:
        - Dynamic quantization: No calibration data required
        - Static quantization: Requires calibration data for better accuracy

        Args:
            model_path: Path to ONNX model file
            output_name: Name for output file
            calibration_data: Optional calibration dataset for static quantization
            quantization_type: "dynamic" or "static"

        Returns:
            Path to quantized ONNX model
        """
        from onnxruntime.quantization import (
            quantize_dynamic,
            quantize_static,
            QuantType,
            CalibrationDataReader,
        )

        logger.info(f"Quantizing ONNX model: {model_path}")

        output_path = self.models_dir / f"{output_name}_int8.onnx"

        if quantization_type == "static" and calibration_data:
            # Static quantization with calibration

            class NumpyCalibrationReader(CalibrationDataReader):
                def __init__(self, data: List[np.ndarray], input_name: str = "input"):
                    self.data = data
                    self.input_name = input_name
                    self.index = 0

                def get_next(self):
                    if self.index >= len(self.data):
                        return None
                    sample = self.data[self.index].astype(np.float32)
                    if len(sample.shape) == 3:
                        sample = np.expand_dims(sample, axis=0)
                    self.index += 1
                    return {self.input_name: sample}

            # Get input name from model
            import onnx

            model = onnx.load(model_path)
            input_name = model.graph.input[0].name

            calibration_reader = NumpyCalibrationReader(
                calibration_data[:100], input_name
            )

            quantize_static(
                model_path,
                str(output_path),
                calibration_reader,
                weight_type=QuantType.QInt8,
            )
        else:
            # Dynamic quantization
            quantize_dynamic(
                model_path,
                str(output_path),
                weight_type=QuantType.QInt8,
            )

        # Log size comparison
        original_size = os.path.getsize(model_path)
        quantized_size = os.path.getsize(output_path)

        logger.info(f"Quantized model saved to {output_path}")
        logger.info(f"Original size: {original_size / 1024 / 1024:.2f} MB")
        logger.info(f"Quantized size: {quantized_size / 1024 / 1024:.2f} MB")

        return output_path

    def load_quantized_tflite(self, model_path: Path) -> "tf.lite.Interpreter":
        """Load a quantized TFLite model.

        Args:
            model_path: Path to .tflite file

        Returns:
            TFLite Interpreter ready for inference
        """
        import tensorflow as tf

        interpreter = tf.lite.Interpreter(model_path=str(model_path))
        interpreter.allocate_tensors()

        logger.info(f"Loaded TFLite model: {model_path}")

        return interpreter

    def load_quantized_onnx(
        self,
        model_path: Path,
        use_gpu: bool = True,
    ) -> "ort.InferenceSession":
        """Load a quantized ONNX model with optimizations.

        Args:
            model_path: Path to .onnx file
            use_gpu: Whether to use GPU acceleration

        Returns:
            ONNX Runtime InferenceSession
        """
        import onnxruntime as ort

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = 4

        providers = []
        if use_gpu:
            available = ort.get_available_providers()
            if "TensorrtExecutionProvider" in available:
                providers.append("TensorrtExecutionProvider")
            if "CUDAExecutionProvider" in available:
                providers.append("CUDAExecutionProvider")
        providers.append("CPUExecutionProvider")

        session = ort.InferenceSession(
            str(model_path),
            sess_options=sess_options,
            providers=providers,
        )

        logger.info(f"Loaded ONNX model: {model_path} with providers: {providers}")

        return session

    def _get_model_size(self, path: str) -> int:
        """Get size of model file or directory.

        Args:
            path: Path to model file or directory

        Returns:
            Size in bytes
        """
        path = Path(path)
        if path.is_file():
            return path.stat().st_size
        elif path.is_dir():
            return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return 0


class QuantizedEmbeddingExtractor:
    """Embedding extractor using quantized ONNX models.

    Provides a unified interface for extracting face embeddings using
    quantized models for improved inference performance.
    """

    def __init__(
        self,
        model_path: Path,
        use_gpu: bool = True,
        input_size: tuple = (224, 224),
    ):
        """Initialize quantized embedding extractor.

        Args:
            model_path: Path to quantized ONNX model
            use_gpu: Whether to use GPU acceleration
            input_size: Model input size (height, width)
        """
        self.input_size = input_size
        self.session = self._load_model(model_path, use_gpu)
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

        logger.info(f"QuantizedEmbeddingExtractor initialized: {model_path}")

    def _load_model(self, model_path: Path, use_gpu: bool):
        """Load ONNX model with appropriate providers."""
        import onnxruntime as ort

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        providers = []
        if use_gpu:
            available = ort.get_available_providers()
            if "CUDAExecutionProvider" in available:
                providers.append("CUDAExecutionProvider")
        providers.append("CPUExecutionProvider")

        return ort.InferenceSession(
            str(model_path),
            sess_options=sess_options,
            providers=providers,
        )

    def extract(self, image: np.ndarray) -> np.ndarray:
        """Extract embedding using quantized model.

        Args:
            image: Face image as numpy array (RGB, any size)

        Returns:
            Embedding vector as 1D numpy array
        """
        # Preprocess
        input_data = self._preprocess(image)

        # Run inference
        outputs = self.session.run([self.output_name], {self.input_name: input_data})

        return outputs[0].flatten().astype(np.float32)

    def extract_batch(self, images: List[np.ndarray]) -> List[np.ndarray]:
        """Extract embeddings for multiple images.

        Args:
            images: List of face images

        Returns:
            List of embedding vectors
        """
        # Stack preprocessed images
        batch = np.stack([self._preprocess(img)[0] for img in images], axis=0)

        # Run batch inference
        outputs = self.session.run([self.output_name], {self.input_name: batch})

        # Split into individual embeddings
        embeddings = outputs[0]
        return [embeddings[i].flatten().astype(np.float32) for i in range(len(images))]

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for model input.

        Args:
            image: Input image (BGR or RGB)

        Returns:
            Preprocessed image as float32 array with batch dimension
        """
        import cv2

        # Resize
        image = cv2.resize(image, self.input_size)

        # Convert BGR to RGB if needed (assumes 3 channels)
        if len(image.shape) == 3 and image.shape[2] == 3:
            # Normalize to [0, 1]
            image = image.astype(np.float32) / 255.0

        # Add batch dimension
        return np.expand_dims(image, axis=0)


class TFLiteEmbeddingExtractor:
    """Embedding extractor using quantized TFLite models."""

    def __init__(self, model_path: Path, input_size: tuple = (224, 224)):
        """Initialize TFLite embedding extractor.

        Args:
            model_path: Path to .tflite model
            input_size: Model input size (height, width)
        """
        import tensorflow as tf

        self.input_size = input_size
        self.interpreter = tf.lite.Interpreter(model_path=str(model_path))
        self.interpreter.allocate_tensors()

        # Get input/output details
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

        # Check if model expects int8 input
        self.input_dtype = self.input_details[0]["dtype"]
        self.input_scale = self.input_details[0].get("quantization", (1.0, 0))[0]
        self.input_zero_point = self.input_details[0].get("quantization", (1.0, 0))[1]

        logger.info(f"TFLiteEmbeddingExtractor initialized: {model_path}")

    def extract(self, image: np.ndarray) -> np.ndarray:
        """Extract embedding using TFLite model.

        Args:
            image: Face image as numpy array

        Returns:
            Embedding vector
        """
        # Preprocess
        input_data = self._preprocess(image)

        # Set input tensor
        self.interpreter.set_tensor(self.input_details[0]["index"], input_data)

        # Run inference
        self.interpreter.invoke()

        # Get output
        output = self.interpreter.get_tensor(self.output_details[0]["index"])

        return output.flatten().astype(np.float32)

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for TFLite model."""
        import cv2

        # Resize
        image = cv2.resize(image, self.input_size)

        # Normalize
        image = image.astype(np.float32) / 255.0

        # Quantize if needed
        if self.input_dtype == np.int8:
            image = (image / self.input_scale + self.input_zero_point).astype(np.int8)

        # Add batch dimension
        return np.expand_dims(image, axis=0)
