"""Canonical digest of the puzzle landmark traces bio actually accepted.

Used by the attested puzzle binding (identity-core-api
``docs/ATTESTED_PUZZLE_BINDING.md``). A hardware-attested Android client signs a
payload that contains the digest of the traces it submitted; identity-core-api
asks bio for the digest of the traces bio SCORED (``include_trace_digest`` on the
verdict) and verifies the signature over that value. A signature therefore only
verifies when the attested app signed exactly the traces that passed the server
re-scoring, in the issued order.

Encoding (all integers big-endian, every trace value is an integer on the wire):

Per accepted challenge (``FPT1``)::

    b"FPT1"
    u8   len(action) || action (ASCII, the ChallengeType value, e.g. "blink")
    i32  version || i32 frame_width || i32 frame_height
    u32  frame count
    per frame:
        i64 t
        u8  mask (bit0 = face ``f`` present, bit1 = hand ``h`` present)
        f:  96 x i32 when present
        h:  63 x i32 when present

    challenge_digest = SHA-256(above)

Session (``FPS1``), over the ACCEPTED challenges in ISSUED order::

    b"FPS1" || u32 n || challenge_digest[0] || ... || challenge_digest[n-1]

    trace_digest = lowercase hex SHA-256(above)

The same encoding is implemented by the Android client (client-apps
``shared/.../attestation/PuzzleTraceDigest.kt``); a shared golden vector pins it
on both sides (``tests/unit/application/services/test_puzzle_trace_digest.py``).
"""

from __future__ import annotations

import hashlib
import struct
from typing import Any, Iterable, Mapping, Optional, Sequence

TRACE_MAGIC = b"FPT1"
SESSION_MAGIC = b"FPS1"


def _ints(values: Optional[Sequence[Any]]) -> bytes:
    if values is None:
        return b""
    return struct.pack(f">{len(values)}i", *(int(v) for v in values))


def challenge_trace_digest(action: str, trace: Mapping[str, Any]) -> bytes:
    """SHA-256 of one accepted challenge's canonical trace encoding."""
    action_bytes = str(action).encode("ascii")
    if len(action_bytes) > 255:
        raise ValueError("action name too long")
    frames = trace.get("frames") or []
    out = bytearray()
    out += TRACE_MAGIC
    out += struct.pack(">B", len(action_bytes)) + action_bytes
    out += struct.pack(
        ">iiiI",
        int(trace.get("version", 0)),
        int(trace.get("frame_width", 0)),
        int(trace.get("frame_height", 0)),
        len(frames),
    )
    for frame in frames:
        f = frame.get("f")
        h = frame.get("h")
        mask = (1 if f is not None else 0) | (2 if h is not None else 0)
        out += struct.pack(">qB", int(frame.get("t", 0)), mask)
        out += _ints(f)
        out += _ints(h)
    return hashlib.sha256(bytes(out)).digest()


def session_trace_digest(challenge_digests: Iterable[bytes]) -> str:
    """Hex SHA-256 over the per-challenge digests in issued order."""
    digests = list(challenge_digests)
    out = bytearray(SESSION_MAGIC)
    out += struct.pack(">I", len(digests))
    for d in digests:
        if len(d) != 32:
            raise ValueError("challenge digest must be 32 bytes")
        out += d
    return hashlib.sha256(bytes(out)).hexdigest()


__all__ = ["challenge_trace_digest", "session_trace_digest"]
