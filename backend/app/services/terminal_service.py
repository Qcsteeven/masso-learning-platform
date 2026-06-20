"""Terminal service — WebSocket ↔ Docker exec bridge (Phase 5.3)."""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging

import docker
import docker.errors
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

_log = logging.getLogger(__name__)

# Chunk size for reading from the Docker exec socket
_READ_CHUNK = 4096


async def _read_docker_to_ws(sock: object, ws: WebSocket) -> None:
    """Read raw bytes from the Docker exec socket and forward to WebSocket as stdout."""
    loop = asyncio.get_event_loop()
    try:
        while True:
            # Docker SDK socket is a synchronous socket; offload to thread pool
            data: bytes = await loop.run_in_executor(None, sock._sock.recv, _READ_CHUNK)  # type: ignore[union-attr]
            if not data:
                break
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.send_text(json.dumps({"type": "stdout", "data": data.decode("utf-8", errors="replace")}))
    except (OSError, AttributeError):
        pass  # Socket closed — normal exit
    except WebSocketDisconnect:
        pass


async def _write_ws_to_docker(ws: WebSocket, sock: object, exec_id: str, client: object) -> None:
    """Receive messages from the WebSocket and forward to the Docker exec socket."""
    loop = asyncio.get_event_loop()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")
            if msg_type == "stdin":
                payload: str = msg.get("data", "")
                await loop.run_in_executor(None, sock._sock.send, payload.encode())  # type: ignore[union-attr]
            elif msg_type == "resize":
                cols = int(msg.get("cols", 80))
                rows = int(msg.get("rows", 24))
                await asyncio.to_thread(
                    client.api.exec_resize,  # type: ignore[union-attr]
                    exec_id,
                    height=rows,
                    width=cols,
                )
            elif msg_type == "close":
                break
    except WebSocketDisconnect:
        pass
    except (OSError, RuntimeError):
        pass


async def _bridge(ws: WebSocket, sock: object, exec_id: str, client: object) -> None:
    """Run the bidirectional Docker ↔ WebSocket bridge until either side closes."""
    reader = asyncio.create_task(_read_docker_to_ws(sock, ws))
    writer = asyncio.create_task(_write_ws_to_docker(ws, sock, exec_id, client))

    # Wait for whichever side finishes first, then cancel the other
    done, pending = await asyncio.wait(
        [reader, writer],
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    # Close the Docker socket
    with contextlib.suppress(OSError, AttributeError):
        sock._sock.close()  # type: ignore[union-attr]

    # Gracefully close WebSocket if still open
    if ws.client_state == WebSocketState.CONNECTED:
        with contextlib.suppress(Exception):  # noqa: BLE001
            await ws.close(1000)


class TerminalService:
    """Bridges a WebSocket connection to a /bin/bash shell inside a Docker container."""

    async def attach_to_container(
        self,
        session_id: str,
        ws: WebSocket,
    ) -> None:
        """Open a bash exec inside the sandbox container and bridge it to the WebSocket.

        The container must be named ``masso-{session_id}``.  If not found,
        sends an error frame and closes with code 1011.
        """
        client: docker.DockerClient = await asyncio.to_thread(docker.from_env)

        container_name = f"masso-{session_id}"
        try:
            container = await asyncio.to_thread(client.containers.get, container_name)
        except docker.errors.NotFound:
            _log.warning("Sandbox container %r not found for session %s", container_name, session_id)
            await ws.send_text(json.dumps({"type": "error", "message": "Sandbox not running"}))
            await ws.close(1011)
            return
        except docker.errors.APIError as exc:
            _log.error("Docker API error for session %s: %s", session_id, exc)
            await ws.send_text(json.dumps({"type": "error", "message": "Docker error"}))
            await ws.close(1011)
            return

        # Create a bash exec instance with a PTY
        exec_resp = await asyncio.to_thread(
            client.api.exec_create,
            container.id,
            "/bin/bash",
            stdin=True,
            tty=True,
            stdout=True,
            stderr=True,
        )
        exec_id: str = exec_resp["Id"]

        # Start exec and get the socket (detach=False, socket=True → raw socket)
        sock = await asyncio.to_thread(
            client.api.exec_start,
            exec_id,
            socket=True,
        )

        await _bridge(ws, sock, exec_id, client)


_terminal_service: TerminalService | None = None


def get_terminal_service() -> TerminalService:
    """FastAPI dependency — returns the singleton TerminalService."""
    global _terminal_service  # noqa: PLW0603
    if _terminal_service is None:
        _terminal_service = TerminalService()
    return _terminal_service
