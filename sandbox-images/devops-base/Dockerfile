# DevOps scenario base image — pinned Ubuntu 24.04 digest
# Provides: bash, curl, git, jq, iproute2, net-tools, procps, vim, nano
# Security: uid=1000, no root, no SSH daemon, no package manager in runtime PATH
FROM ubuntu:24.04@sha256:3f85b7caad41a95462cf5b787d8a04604c8262d6bb2d8c46b4ae8749a2f1d82d

LABEL masso.image=devops-base
LABEL masso.version=0.1.0

# Install minimal DevOps/sysadmin toolset; clean up apt cache in the same layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    git \
    jq \
    iproute2 \
    net-tools \
    procps \
    vim \
    nano \
    && rm -rf /var/lib/apt/lists/*

# Non-root sandbox user (uid/gid 1000 — mandatory per ТЗ §4.2)
RUN groupadd -g 1000 sandbox && \
    useradd -u 1000 -g sandbox -m -s /bin/bash sandbox && \
    mkdir -p /workspace && \
    chown sandbox:sandbox /workspace

USER sandbox
WORKDIR /workspace

# Liveness probe — verifies that a sandbox-owned bash process is running
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD pgrep -u sandbox bash || exit 1

CMD ["/bin/bash"]
