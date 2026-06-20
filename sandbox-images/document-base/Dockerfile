# Document scenario base image — ultra-minimal, web-based trainer
# Document scenarios run primarily in the browser; this container is a thin
# process host for rule_match / cosine-similarity verification calls only.
# Provides: bash, python3 (for verification scripts)
# Security: uid=1000, no root, no SSH, no curl, no apt in runtime
FROM ubuntu:24.04@sha256:3f85b7caad41a95462cf5b787d8a04604c8262d6bb2d8c46b4ae8749a2f1d82d

LABEL masso.image=document-base
LABEL masso.version=0.1.0

# Minimal runtime: bash + python3 for verification scripts
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    python3 \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Non-root sandbox user (uid/gid 1000 — mandatory per ТЗ §4.2)
RUN groupadd -g 1000 sandbox && \
    useradd -u 1000 -g sandbox -m -s /bin/bash sandbox && \
    mkdir -p /workspace && \
    chown sandbox:sandbox /workspace

USER sandbox
WORKDIR /workspace

# Liveness probe — container stays alive for the session duration
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD pgrep -u sandbox -f "sleep" || exit 1

# Idle process — document scenarios are web-only; container acts as anchor
CMD ["/bin/bash", "-c", "while true; do sleep 3600; done"]
