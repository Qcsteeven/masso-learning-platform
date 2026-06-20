"""Sandbox Manager — Docker-backed isolated container lifecycle.

Responsible for deploying, monitoring, and cleaning up per-session sandbox
containers according to ТЗ §4.2 and §4.9 security requirements:
  - --no-new-privileges, --cap-drop ALL
  - deny-by-default network (internal bridge per session)
  - non-root uid=1000
  - cleanup within 30 seconds of session termination
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import TypedDict

import docker
import docker.errors
from fastapi import HTTPException, status

from app.core.errors import SANDBOX_LIMIT_EXCEEDED
from app.db.redis import get_redis, lock_key, session_state_key

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Profile → image mapping (pinned to version tags, never "latest")
# ---------------------------------------------------------------------------
_PROFILE_IMAGE_MAP: dict[str, str] = {
    "devops-base": "masso/devops-base:0.1.0",
    "security-base": "masso/security-base:0.1.0",
    "document-base": "masso/document-base:0.1.0",
}

# Default resource limits — overridden by sandbox_profile metadata when available
_DEFAULT_MEM_LIMIT = "512m"
_DEFAULT_NANO_CPUS = int(1e9)  # 1 CPU
_LOCK_TTL_SECONDS = 30
_STATE_TTL_SECONDS = 86400  # 24 h
_STOP_TIMEOUT_SECONDS = 10


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------
class ContainerInfo(TypedDict):
    container_id: str
    session_id: str
    image: str
    sandbox_url: str   # terminal WebSocket URL
    started_at: str    # ISO-8601 datetime
    status: str        # "running" | "stopped" | "error"


# ---------------------------------------------------------------------------
# SandboxManager
# ---------------------------------------------------------------------------
class SandboxManager:
    """Manages the full lifecycle of per-session sandbox containers."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _docker_client(self) -> docker.DockerClient:
        """Return a Docker client connected to the local daemon."""
        return docker.from_env()

    def _container_name(self, session_id: str) -> str:
        return f"masso-{session_id}"

    def _network_name(self, session_id: str) -> str:
        return f"masso-session-{session_id}"

    def _sandbox_url(self, session_id: str) -> str:
        return f"/ws/sessions/{session_id}/terminal"

    # ------------------------------------------------------------------
    # deploy()
    # ------------------------------------------------------------------
    async def deploy(self, session_id: str, sandbox_profile: str) -> ContainerInfo:
        """Deploy a sandbox container for *session_id*.

        Steps:
        1. Acquire distributed Redis lock (NX EX 30).
        2. Resolve profile → image; verify image exists locally.
        3. Create per-session isolated bridge network (internal=True).
        4. Start container with mandatory security flags.
        5. Persist ContainerInfo to Redis (TTL 24 h).

        Raises:
            HTTPException(409) — if another deploy is in progress for this session.
            HTTPException(503) — if the image is not found locally.
        """
        redis = get_redis()

        # 1. Distributed lock — prevents double-deploy for the same session
        lock_acquired = await redis.set(lock_key(session_id), "1", nx=True, ex=_LOCK_TTL_SECONDS)
        if not lock_acquired:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=SANDBOX_LIMIT_EXCEEDED,
            )

        image_name = _PROFILE_IMAGE_MAP.get(sandbox_profile)
        if image_name is None:
            await redis.delete(lock_key(session_id))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=SANDBOX_LIMIT_EXCEEDED,
            )

        try:
            container_info = await asyncio.to_thread(
                self._deploy_sync,
                session_id,
                image_name,
            )
        except HTTPException:
            await redis.delete(lock_key(session_id))
            raise
        except Exception as exc:
            await redis.delete(lock_key(session_id))
            logger.exception("Unexpected error deploying sandbox for session %s", session_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=SANDBOX_LIMIT_EXCEEDED,
            ) from exc

        # 5. Persist state in Redis
        await redis.hset(  # type: ignore[misc]
            session_state_key(session_id),
            mapping={
                "container_id": container_info["container_id"],
                "session_id": container_info["session_id"],
                "image": container_info["image"],
                "sandbox_url": container_info["sandbox_url"],
                "started_at": container_info["started_at"],
                "status": container_info["status"],
            },
        )
        await redis.expire(session_state_key(session_id), _STATE_TTL_SECONDS)

        logger.info(
            "Sandbox deployed: session=%s container=%s image=%s",
            session_id,
            container_info["container_id"][:12],
            image_name,
        )
        return container_info

    def _deploy_sync(self, session_id: str, image_name: str) -> ContainerInfo:
        """Synchronous Docker calls — must be run via asyncio.to_thread."""
        client = self._docker_client()

        # Verify image exists locally — never auto-pull in production
        try:
            client.images.get(image_name)
        except docker.errors.ImageNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=SANDBOX_LIMIT_EXCEEDED,
            ) from exc

        # 3. Create per-session isolated bridge network (deny-by-default)
        network = client.networks.create(
            self._network_name(session_id),
            driver="bridge",
            internal=True,  # no external connectivity by default (ТЗ §4.9)
            labels={"masso.session_id": session_id, "masso.role": "sandbox"},
        )

        try:
            # 4. Start container with mandatory security flags (ТЗ §4.2)
            container = client.containers.run(
                image=image_name,
                detach=True,
                name=self._container_name(session_id),
                network=network.name,
                security_opt=["no-new-privileges:true"],
                cap_drop=["ALL"],
                read_only=False,  # /workspace and /tmp need writes
                tmpfs={"/tmp": "size=64m,mode=1777"},
                mem_limit=_DEFAULT_MEM_LIMIT,
                nano_cpus=_DEFAULT_NANO_CPUS,
                labels={
                    "masso.role": "sandbox",
                    "masso.session_id": session_id,
                },
                user="1000:1000",
                stdin_open=True,
                tty=True,
            )
        except Exception:
            # Roll back network if container start fails
            with contextlib.suppress(Exception):
                network.remove()
            raise

        return ContainerInfo(
            container_id=container.id,
            session_id=session_id,
            image=image_name,
            sandbox_url=self._sandbox_url(session_id),
            started_at=datetime.now(UTC).isoformat(),
            status="running",
        )

    # ------------------------------------------------------------------
    # stop()
    # ------------------------------------------------------------------
    async def stop(self, session_id: str) -> None:
        """Stop (but do not remove) the sandbox container for *session_id*."""
        redis = get_redis()

        await asyncio.to_thread(self._stop_sync, session_id)

        # Update Redis state
        await redis.hset(session_state_key(session_id), "status", "stopped")  # type: ignore[misc]
        logger.info("Sandbox stopped: session=%s", session_id)

    def _stop_sync(self, session_id: str) -> None:
        client = self._docker_client()
        try:
            container = client.containers.get(self._container_name(session_id))
            container.stop(timeout=_STOP_TIMEOUT_SECONDS)
        except docker.errors.NotFound:
            logger.warning("stop(): container not found for session %s", session_id)

    # ------------------------------------------------------------------
    # get_status()
    # ------------------------------------------------------------------
    async def get_status(self, session_id: str) -> str:
        """Return "running" | "stopped" | "unknown"."""
        redis = get_redis()

        cached = await redis.hget(session_state_key(session_id), "status")  # type: ignore[misc]
        if cached:
            return str(cached)

        # Fallback: query Docker directly (off the event loop)
        result: str = await asyncio.to_thread(self._get_status_sync, session_id)
        return result

    def _get_status_sync(self, session_id: str) -> str:
        client = self._docker_client()
        try:
            container = client.containers.get(self._container_name(session_id))
            return "running" if container.status == "running" else "stopped"
        except docker.errors.NotFound:
            return "unknown"

    # ------------------------------------------------------------------
    # exec_in_container()
    # ------------------------------------------------------------------
    async def exec_in_container(
        self,
        session_id: str,
        cmd: str,
    ) -> tuple[str, str, int]:
        """Execute *cmd* inside the session container.

        Returns (stdout, stderr, exit_code).
        """
        result: tuple[str, str, int] = await asyncio.to_thread(
            self._exec_sync, session_id, cmd
        )
        return result

    def _exec_sync(self, session_id: str, cmd: str) -> tuple[str, str, int]:
        client = self._docker_client()
        try:
            container = client.containers.get(self._container_name(session_id))
        except docker.errors.NotFound:
            return ("", f"Container masso-{session_id} not found", 1)

        exec_result = container.exec_run(
            cmd,
            user="1000",
            demux=True,  # separate stdout / stderr
        )
        exit_code: int = exec_result.exit_code or 0
        stdout_bytes, stderr_bytes = exec_result.output or (b"", b"")
        stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
        stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")
        return (stdout, stderr, exit_code)

    # ------------------------------------------------------------------
    # cleanup()
    # ------------------------------------------------------------------
    async def cleanup(self, session_id: str) -> None:
        """Remove container + network + Redis state.

        Target: complete within 30 seconds (ТЗ §4.9, SLA).
        """
        await asyncio.to_thread(self._cleanup_sync, session_id)

        redis = get_redis()
        await redis.delete(session_state_key(session_id))
        await redis.delete(lock_key(session_id))
        logger.info("Sandbox cleaned up: session=%s", session_id)

    def _cleanup_sync(self, session_id: str) -> None:
        client = self._docker_client()

        # 1. Stop + remove container
        try:
            container = client.containers.get(self._container_name(session_id))
            container.stop(timeout=_STOP_TIMEOUT_SECONDS)
            container.remove(force=True)
            logger.debug("Container removed: %s", self._container_name(session_id))
        except docker.errors.NotFound:
            logger.warning("cleanup(): container not found for session %s", session_id)

        # 2. Remove per-session network
        networks = client.networks.list(
            filters={"label": f"masso.session_id={session_id}"}
        )
        for net in networks:
            try:
                net.remove()
                logger.debug("Network removed: %s", net.name)
            except Exception as exc:
                logger.warning("Failed to remove network %s: %s", net.name, exc)


# ---------------------------------------------------------------------------
# Singleton + FastAPI dependency
# ---------------------------------------------------------------------------
_manager: SandboxManager | None = None


def get_sandbox_manager() -> SandboxManager:
    """Return the process-level SandboxManager singleton."""
    global _manager
    if _manager is None:
        _manager = SandboxManager()
    return _manager
