"""Sandbox image utilities.

Provides helpers to validate that a required image exists in the local Docker
daemon cache.  Images are NEVER pulled automatically — pulling must be an
explicit operator action to avoid uncontrolled network traffic inside the
sandbox pipeline.
"""
from __future__ import annotations

import asyncio
import logging

import docker
import docker.errors

logger = logging.getLogger(__name__)

# Known managed images (profile → image:tag)
MANAGED_IMAGES: dict[str, str] = {
    "devops-base": "masso/devops-base:0.1.0",
    "security-base": "masso/security-base:0.1.0",
    "document-base": "masso/document-base:0.1.0",
}


async def validate_image(image_name: str) -> bool:
    """Return True if *image_name* exists in the local Docker image cache.

    Never pulls the image automatically.  Runs the blocking Docker SDK call
    off the event loop via asyncio.to_thread.
    """
    return await asyncio.to_thread(_validate_image_sync, image_name)


def _validate_image_sync(image_name: str) -> bool:
    try:
        docker.from_env().images.get(image_name)
        logger.debug("Image found locally: %s", image_name)
        return True
    except docker.errors.ImageNotFound:
        logger.warning("Image not found locally: %s", image_name)
        return False
    except Exception as exc:
        logger.error("Error checking image %s: %s", image_name, exc)
        return False


async def list_missing_images() -> list[str]:
    """Return a list of managed image names that are absent from the local cache.

    Useful for startup health checks and operator tooling.
    """
    missing: list[str] = []
    for _profile, image in MANAGED_IMAGES.items():
        if not await validate_image(image):
            missing.append(image)
    return missing
