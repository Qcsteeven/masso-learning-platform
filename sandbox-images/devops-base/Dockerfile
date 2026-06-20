# DevOps sandbox image — Ubuntu 24.04
FROM ubuntu:24.04
LABEL masso.image=devops-base
LABEL masso.version=0.1.0
RUN apt-get update && apt-get install -y --no-install-recommends bash curl git jq iproute2 net-tools procps vim nano && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /workspace && chown ubuntu:ubuntu /workspace
USER ubuntu
WORKDIR /workspace
HEALTHCHECK --interval=10s --timeout=5s --retries=3 CMD pgrep -u ubuntu bash || exit 1
CMD ["/bin/bash"]
