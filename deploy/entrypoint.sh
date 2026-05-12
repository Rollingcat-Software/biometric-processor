#!/bin/sh
# ============================================================================
# biometric-processor entrypoint shim
# ----------------------------------------------------------------------------
# Runs as root so it can:
#   1. chown any externally-mounted /tmp/.deepface cache volume to 100:101
#      (uid/gid of the `app` user). Without this, a root-owned named volume
#      shadows the image-baked weights and DeepFace cannot write its cache.
#      This is the 4th-recurrence pattern from feedback_readonly_rootfs_cache_dirs
#      (DeepFace + Numba + UniFace, now MiniFASNet) — solved here at
#      defense-in-depth layer 2 (layer 1 = bake weights into the image).
#
#   2. Seed missing model files from /opt/baked-models into the mounted cache
#      volume. After `docker volume rm biometric-processor_biometric_models`
#      the volume comes back empty and root-owned — without this seed, the
#      operator has to remember to manually `docker cp` the MiniFASNet
#      weights (which is what bit us today). With the seed, the named volume
#      is self-healing from the image layer.
#
# After both steps complete, the shim execs the original CMD as uid 100 via
# `gosu`. Both seed steps are best-effort (`|| true`) and never block boot.
#
# This script is a no-op if there is no volume mount at /tmp/.deepface — the
# baked /opt/baked-models layer is sufficient on its own (DEEPFACE_HOME is
# overridden to /opt/baked-models in that path).
# ============================================================================
set -eu

DEEPFACE_CACHE_DIR="${DEEPFACE_HOME:-/tmp/.deepface}"
BAKED_MODELS_DIR="/opt/baked-models/.deepface"

# Only attempt cache-volume initialisation if a directory is actually mounted
# (or createable) at the cache location. Under read_only:true rootfs this is
# only writable if a tmpfs or named volume covers it.
if [ -d "${DEEPFACE_CACHE_DIR}" ] || mkdir -p "${DEEPFACE_CACHE_DIR}" 2>/dev/null; then
    # 1. Defense-in-depth: ensure the mount is owned by uid 100 / gid 101.
    chown -R 100:101 "${DEEPFACE_CACHE_DIR}" 2>/dev/null || true
    chmod -R u+rwX,go+rX "${DEEPFACE_CACHE_DIR}" 2>/dev/null || true

    # 2. Seed missing weight files from the baked image layer. We copy
    #    only when the destination file is absent so we never overwrite
    #    an operator's deliberate model rotation.
    if [ -d "${BAKED_MODELS_DIR}/weights" ]; then
        mkdir -p "${DEEPFACE_CACHE_DIR}/.deepface/weights" 2>/dev/null || true
        for src in "${BAKED_MODELS_DIR}"/weights/*; do
            [ -f "${src}" ] || continue
            name="$(basename "${src}")"
            dst="${DEEPFACE_CACHE_DIR}/.deepface/weights/${name}"
            if [ ! -f "${dst}" ]; then
                cp "${src}" "${dst}" 2>/dev/null || true
                chown 100:101 "${dst}" 2>/dev/null || true
                chmod 0644 "${dst}" 2>/dev/null || true
            fi
        done
    fi
fi

# Drop privileges and exec the CMD. If we're somehow already non-root (e.g.
# docker --user override), skip gosu and exec directly so we don't fail.
if [ "$(id -u)" = "0" ]; then
    exec gosu app "$@"
else
    exec "$@"
fi
