# Document sandbox image — Ubuntu 24.04 minimal
FROM ubuntu:24.04
LABEL masso.image=document-base
LABEL masso.version=0.1.0
RUN apt-get update && apt-get install -y --no-install-recommends bash python3 python3-venv && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /workspace && chown ubuntu:ubuntu /workspace
USER ubuntu
WORKDIR /workspace
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD pgrep -u ubuntu -f sleep || exit 1
CMD ["/bin/bash", "-c", "while true; do sleep 3600; done"]
