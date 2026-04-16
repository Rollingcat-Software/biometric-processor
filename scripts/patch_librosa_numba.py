"""Patch librosa's audio.py to replace the numba @stencil/@guvectorize
zero_crossings implementation with pure numpy.

Problem:
    librosa 0.10.x uses @stencil + @guvectorize from numba for zero_crossings.
    On Python 3.12 with numba >= 0.59, calling a @stencil function inside
    @guvectorize raises:
        AttributeError: 'function' object has no attribute 'get_call_template'
    This crash happens at module import time (not at call time), so
    NUMBA_DISABLE_JIT=1 does NOT help — guvectorize compiles eagerly.

Fix:
    Replace the numba-decorated block with an equivalent pure numpy/scipy
    implementation. The zero_crossings function is only used by librosa
    internally; Resemblyzer only calls librosa.feature.melspectrogram and
    librosa.resample, neither of which calls zero_crossings — but the crash
    happens because importing librosa.feature.spectral imports
    librosa.core.audio, which triggers the @guvectorize at module load.

Run this script once after pip install (done in Dockerfile RUN step).
"""

import re
import sys
from pathlib import Path

LIBROSA_AUDIO = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages" / "librosa" / "core" / "audio.py"

if not LIBROSA_AUDIO.exists():
    # Try alternate location
    import librosa
    LIBROSA_AUDIO = Path(librosa.__file__).parent / "core" / "audio.py"

print(f"Patching: {LIBROSA_AUDIO}")

text = LIBROSA_AUDIO.read_text(encoding="utf-8")

# Check if already patched
if "# PATCHED: numba-free zero_crossings" in text:
    print("Already patched, skipping.")
    sys.exit(0)

# The block to replace: from `from numba import ...` import line,
# plus the @stencil and @guvectorize decorated functions.
# We replace with:
#   1. Remove the numba import
#   2. Replace _zc_stencil and _zc_wrapper with pure numpy equivalents

OLD_IMPORT = "from numba import jit, stencil, guvectorize"
NEW_IMPORT = "from numba import jit  # stencil/guvectorize removed by patch_librosa_numba.py"

if OLD_IMPORT not in text:
    print(f"ERROR: Could not find numba import line. Librosa version may differ.")
    print(f"  Expected: {OLD_IMPORT!r}")
    sys.exit(1)

text = text.replace(OLD_IMPORT, NEW_IMPORT, 1)

# Replace the @stencil block + @guvectorize block with pure numpy implementations
OLD_STENCIL_BLOCK = '''@stencil  # type: ignore
def _zc_stencil(x: np.ndarray, threshold: float, zero_pos: bool) -> np.ndarray:
    """Stencil to compute zero crossings"""
    x0 = x[0]
    if -threshold <= x0 <= threshold:
        x0 = 0

    x1 = x[-1]
    if -threshold <= x1 <= threshold:
        x1 = 0

    if zero_pos:
        return np.signbit(x0) != np.signbit(x1)  # type: ignore
    else:
        return np.sign(x0) != np.sign(x1)  # type: ignore


@guvectorize(
    [
        "void(float32[:], float32, bool_, bool_[:])",
        "void(float64[:], float64, bool_, bool_[:])",
    ],
    "(n),(),()->(n)",
    cache=True,
    nopython=True,
)  # type: ignore
def _zc_wrapper(
    x: np.ndarray,
    threshold: float,
    zero_pos: bool,
    y: np.ndarray,
) -> None:  # pragma: no cover
    """Vectorized wrapper for zero crossing stencil"""
    y[:] = _zc_stencil(x, threshold, zero_pos)'''

NEW_STENCIL_BLOCK = '''# PATCHED: numba-free zero_crossings (patch_librosa_numba.py)
# Replaces @stencil + @guvectorize with pure numpy — identical semantics.
def _zc_numpy(
    x: np.ndarray,
    threshold: float = 1e-10,
    zero_pos: bool = True,
) -> np.ndarray:
    """Pure numpy zero crossing computation (replaces numba stencil)."""
    # Clip near-zero values to exactly zero
    x_clipped = x.copy()
    x_clipped[np.abs(x_clipped) <= threshold] = 0.0
    # Shift by one sample to get consecutive pairs
    x0 = x_clipped[..., :-1]
    x1 = x_clipped[..., 1:]
    if zero_pos:
        zc = np.signbit(x0) != np.signbit(x1)
    else:
        zc = np.sign(x0) != np.sign(x1)
    # Prepend False for the first sample (no previous sample)
    pad_shape = list(x.shape)
    pad_shape[-1] = 1
    return np.concatenate([np.zeros(pad_shape, dtype=bool), zc], axis=-1)'''

if OLD_STENCIL_BLOCK not in text:
    print("ERROR: Could not find the @stencil/@guvectorize block to replace.")
    print("  The librosa version may differ from expected 0.10.x.")
    # Print what we find around line 1141
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if "stencil" in line or "guvectorize" in line:
            print(f"  Line {i+1}: {line}")
    sys.exit(1)

text = text.replace(OLD_STENCIL_BLOCK, NEW_STENCIL_BLOCK, 1)

# Now patch zero_crossings to call _zc_numpy instead of _zc_wrapper
# Find the internal call to _zc_wrapper inside zero_crossings and replace
OLD_ZC_CALL = "    zc = _zc_wrapper(y, threshold, zero_pos)"
NEW_ZC_CALL = "    zc = _zc_numpy(y, threshold, zero_pos)"

if OLD_ZC_CALL in text:
    text = text.replace(OLD_ZC_CALL, NEW_ZC_CALL, 1)
    print("  Patched _zc_wrapper call to _zc_numpy")
else:
    # Alternative: _zc_wrapper might be called differently — find it
    matches = [(i, l) for i, l in enumerate(text.split("\n")) if "_zc_wrapper" in l]
    if matches:
        print(f"  WARNING: _zc_wrapper found at lines {[m[0]+1 for m in matches]} but not as expected.")
        print(f"  Manual inspection may be needed.")
    else:
        print("  NOTE: No _zc_wrapper call found in zero_crossings body — may be OK.")

LIBROSA_AUDIO.write_text(text, encoding="utf-8")
print("Patch applied successfully.")

# Verify the patch works
try:
    import importlib
    import librosa.core.audio  # noqa: F401
    print("Verification: librosa.core.audio imports without error.")
except Exception as e:
    print(f"Verification FAILED: {e}")
    sys.exit(1)
