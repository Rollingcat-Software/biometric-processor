"""Face embedding pipeline: channel order and the id recorded with each template.

Facenet512's weights are davidsandberg/facenet's Inception ResNet v1 (2018),
converted to Keras by DeepFace. That model was trained on images decoded by
``tf.image.decode_image(contents, 3)`` (``src/facenet.py``,
``create_input_pipeline``), which yields RGB, and DeepFace's own FaceNet page
says the model expects 160x160 RGB images. DeepFace 0.0.98 ``represent``
nevertheless flips the RGB face from ``extract_faces`` to BGR before the forward
pass (``modules/representation.py``, comment ``# rgb to bgr``). Feeding RGB is
the fix; on LFW View 2 the browser pipeline scored EER 2.54% in RGB against
3.27% in BGR (fivucsas-papers ``bench/lfw-browser/aligned``).

Embeddings are comparable only within one pipeline. Each stored template
records the pipeline id under ``EMBEDDING_PIPELINE_METADATA_KEY`` in
``face_embeddings.metadata``. Rows written before this existed have no id; they
were computed from BGR input and must be re-enrolled. The web client defines its
own id the same way (web-app ``embeddingPipeline.ts``).
"""

from typing import Final, Literal

ChannelOrder = Literal["RGB", "BGR"]

FACENET_CHANNEL_ORDER: Final[ChannelOrder] = "RGB"

# The 512-dim store holds Facenet512 templates (FACE_RECOGNITION_MODEL in
# production); the id names that model and the channel order it was fed.
SERVER_EMBEDDING_PIPELINE: Final[str] = f"server-deepface-facenet512-{FACENET_CHANNEL_ORDER.lower()}"

EMBEDDING_PIPELINE_METADATA_KEY: Final[str] = "embedding_pipeline"
