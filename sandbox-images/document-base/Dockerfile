# Document scenario base image — web-based trainer, minimal container
# Used as a thin process for document scenarios that run in the browser.
FROM ubuntu:24.04@sha256:3f85b7caad41a95462cf5b787d8a04604c8262d6bb2d8c46b4ae8749a2f1d82d

LABEL masso.image=document-base
LABEL masso.version=0.1.0

RUN groupadd -g 1000 sandbox && useradd -u 1000 -g sandbox -m -s /bin/bash sandbox
RUN mkdir -p /workspace && chown sandbox:sandbox /workspace

USER sandbox
WORKDIR /workspace

CMD ["/bin/bash", "-c", "while true; do sleep 3600; done"]
