# Security sandbox image — Ubuntu 24.04
FROM ubuntu:24.04
LABEL masso.image=security-base
LABEL masso.version=0.1.0
RUN apt-get update && apt-get install -y --no-install-recommends bash iproute2 net-tools procps nmap tcpdump && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /workspace && chown ubuntu:ubuntu /workspace
USER ubuntu
WORKDIR /workspace
HEALTHCHECK --interval=10s --timeout=5s --retries=3 CMD pgrep -u ubuntu bash || exit 1
CMD ["/bin/bash"]
