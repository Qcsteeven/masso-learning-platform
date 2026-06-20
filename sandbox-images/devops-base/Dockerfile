# DevOps scenario base image — pinned Ubuntu 24.04
# uid=1000, no root, no SSH, no external curl
FROM ubuntu:24.04@sha256:3f85b7caad41a95462cf5b787d8a04604c8262d6bb2d8c46b4ae8749a2f1d82d

LABEL masso.image=devops-base
LABEL masso.version=0.1.0

# Install tooling needed for DevOps/sysadmin scenarios
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    git \
    jq \
    iproute2 \
    net-tools \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -g 1000 sandbox && useradd -u 1000 -g sandbox -m -s /bin/bash sandbox

# Working directory owned by sandbox user
RUN mkdir -p /workspace && chown sandbox:sandbox /workspace

USER sandbox
WORKDIR /workspace

CMD ["/bin/bash"]
