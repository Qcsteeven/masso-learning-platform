"""Unit tests for SandboxManager (Phase 5.1).

All Docker SDK and Redis calls are mocked — no real daemon or Redis required.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import docker.errors
import pytest
from fastapi import HTTPException

from app.sandbox.manager import _PROFILE_IMAGE_MAP, ContainerInfo, SandboxManager

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

SESSION_ID = "test-session-abc123"
PROFILE = "devops-base"
EXPECTED_IMAGE = _PROFILE_IMAGE_MAP[PROFILE]
CONTAINER_NAME = f"masso-{SESSION_ID}"
NETWORK_NAME = f"masso-session-{SESSION_ID}"


def _make_mock_container(container_id: str = "abc123def456") -> MagicMock:
    container = MagicMock()
    container.id = container_id
    container.status = "running"
    return container


def _make_mock_network(name: str = NETWORK_NAME) -> MagicMock:
    net = MagicMock()
    net.name = name
    return net


def _make_mock_docker_client(
    *,
    image_found: bool = True,
    container: MagicMock | None = None,
    network: MagicMock | None = None,
) -> MagicMock:
    """Return a fully-wired mock DockerClient."""
    client = MagicMock()

    if not image_found:
        client.images.get.side_effect = docker.errors.ImageNotFound("not found")
    else:
        client.images.get.return_value = MagicMock()

    _container = container or _make_mock_container()
    _network = network or _make_mock_network()

    client.networks.create.return_value = _network
    client.containers.run.return_value = _container
    client.containers.get.return_value = _container
    client.networks.list.return_value = [_network]

    return client


@pytest.fixture()
def manager() -> SandboxManager:
    return SandboxManager()


@pytest.fixture()
async def mock_redis() -> AsyncGenerator[AsyncMock]:
    """Patch get_redis() with an AsyncMock that simulates successful lock acquire."""
    redis = AsyncMock()
    redis.set.return_value = True   # lock acquired
    redis.hset.return_value = 1
    redis.expire.return_value = True
    redis.hget.return_value = None
    redis.delete.return_value = 1
    with patch("app.sandbox.manager.get_redis", return_value=redis):
        yield redis


# ---------------------------------------------------------------------------
# deploy() — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_deploy_returns_container_info(
    manager: SandboxManager,
    mock_redis: AsyncMock,
) -> None:
    """deploy() with a found image should return a populated ContainerInfo."""
    mock_client = _make_mock_docker_client(image_found=True)

    with patch.object(manager, "_docker_client", return_value=mock_client):
        info: ContainerInfo = await manager.deploy(SESSION_ID, PROFILE)

    assert info["session_id"] == SESSION_ID
    assert info["image"] == EXPECTED_IMAGE
    assert info["status"] == "running"
    assert info["sandbox_url"] == f"/ws/sessions/{SESSION_ID}/terminal"
    assert info["container_id"]  # non-empty


@pytest.mark.asyncio()
async def test_deploy_passes_security_flags(
    manager: SandboxManager,
    mock_redis: AsyncMock,
) -> None:
    """Container must be started with no-new-privileges and cap_drop=ALL."""
    mock_client = _make_mock_docker_client(image_found=True)

    with patch.object(manager, "_docker_client", return_value=mock_client):
        await manager.deploy(SESSION_ID, PROFILE)

    _call_kwargs = mock_client.containers.run.call_args
    kwargs = _call_kwargs.kwargs if _call_kwargs.kwargs else _call_kwargs[1]

    assert kwargs.get("security_opt") == ["no-new-privileges:true"], (
        "security_opt must contain 'no-new-privileges:true'"
    )
    assert kwargs.get("cap_drop") == ["ALL"], "cap_drop must be ['ALL']"
    assert kwargs.get("user") == "1000:1000", "Container must run as uid=1000"


@pytest.mark.asyncio()
async def test_deploy_creates_internal_network(
    manager: SandboxManager,
    mock_redis: AsyncMock,
) -> None:
    """The per-session network must be created as internal (deny-by-default)."""
    mock_client = _make_mock_docker_client(image_found=True)

    with patch.object(manager, "_docker_client", return_value=mock_client):
        await manager.deploy(SESSION_ID, PROFILE)

    create_kwargs = mock_client.networks.create.call_args
    kwargs = create_kwargs.kwargs if create_kwargs.kwargs else create_kwargs[1]
    assert kwargs.get("internal") is True, "Network must be internal=True (deny-by-default)"
    assert NETWORK_NAME in mock_client.networks.create.call_args[0]


@pytest.mark.asyncio()
async def test_deploy_stores_state_in_redis(
    manager: SandboxManager,
    mock_redis: AsyncMock,
) -> None:
    """ContainerInfo must be persisted to Redis with TTL after deploy."""
    mock_client = _make_mock_docker_client(image_found=True)

    with patch.object(manager, "_docker_client", return_value=mock_client):
        await manager.deploy(SESSION_ID, PROFILE)

    mock_redis.hset.assert_awaited_once()
    mock_redis.expire.assert_awaited_once()


# ---------------------------------------------------------------------------
# deploy() — image not found → 503
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_deploy_raises_503_when_image_missing(
    manager: SandboxManager,
    mock_redis: AsyncMock,
) -> None:
    """deploy() must raise HTTPException(503) when the image is absent locally."""
    mock_client = _make_mock_docker_client(image_found=False)

    with (
        patch.object(manager, "_docker_client", return_value=mock_client),
        pytest.raises(HTTPException) as exc_info,
    ):
        await manager.deploy(SESSION_ID, PROFILE)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio()
async def test_deploy_raises_503_for_unknown_profile(
    manager: SandboxManager,
    mock_redis: AsyncMock,
) -> None:
    """deploy() must raise HTTPException(503) for an unknown sandbox_profile."""
    with pytest.raises(HTTPException) as exc_info:
        await manager.deploy(SESSION_ID, "totally-unknown-profile")

    assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# deploy() — lock already held → 409
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_deploy_raises_409_when_lock_held(manager: SandboxManager) -> None:
    """deploy() must raise HTTPException(409) when the Redis lock is already taken."""
    redis = AsyncMock()
    redis.set.return_value = None  # SET NX returned nil — lock not acquired

    with (
        patch("app.sandbox.manager.get_redis", return_value=redis),
        pytest.raises(HTTPException) as exc_info,
    ):
        await manager.deploy(SESSION_ID, PROFILE)

    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# cleanup() — removes container + network + Redis keys
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_cleanup_removes_container_network_and_redis(
    manager: SandboxManager,
    mock_redis: AsyncMock,
) -> None:
    """cleanup() must stop/remove the container, remove the network, and delete Redis keys."""
    mock_container = _make_mock_container()
    mock_network = _make_mock_network()
    mock_client = _make_mock_docker_client(container=mock_container, network=mock_network)

    with patch.object(manager, "_docker_client", return_value=mock_client):
        await manager.cleanup(SESSION_ID)

    mock_container.stop.assert_called_once_with(timeout=10)
    mock_container.remove.assert_called_once_with(force=True)
    mock_network.remove.assert_called_once()

    # Redis keys must be deleted
    deleted_keys = [str(call.args[0]) for call in mock_redis.delete.call_args_list]
    assert any(SESSION_ID in k for k in deleted_keys), (
        f"session_state_key for {SESSION_ID} was not deleted; deleted: {deleted_keys}"
    )
    assert any("lock" in k for k in deleted_keys), (
        f"lock_key for {SESSION_ID} was not deleted; deleted: {deleted_keys}"
    )


@pytest.mark.asyncio()
async def test_cleanup_tolerates_missing_container(
    manager: SandboxManager,
    mock_redis: AsyncMock,
) -> None:
    """cleanup() must not raise if the container is already gone."""
    mock_client = MagicMock()
    mock_client.containers.get.side_effect = docker.errors.NotFound("gone")
    mock_client.networks.list.return_value = []

    with patch.object(manager, "_docker_client", return_value=mock_client):
        # Should complete without raising
        await manager.cleanup(SESSION_ID)

    # Redis cleanup still happens
    assert mock_redis.delete.await_count == 2


# ---------------------------------------------------------------------------
# get_status()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_get_status_returns_cached_value(
    manager: SandboxManager,
    mock_redis: AsyncMock,
) -> None:
    """get_status() should return the Redis-cached value without hitting Docker."""
    mock_redis.hget.return_value = "running"

    status = await manager.get_status(SESSION_ID)

    assert status == "running"


@pytest.mark.asyncio()
async def test_get_status_falls_back_to_docker(
    manager: SandboxManager,
    mock_redis: AsyncMock,
) -> None:
    """get_status() falls back to Docker when Redis cache is empty."""
    mock_redis.hget.return_value = None
    mock_client = _make_mock_docker_client()

    with patch.object(manager, "_docker_client", return_value=mock_client):
        status = await manager.get_status(SESSION_ID)

    assert status == "running"


# ---------------------------------------------------------------------------
# exec_in_container()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_exec_returns_stdout_stderr_exit_code(
    manager: SandboxManager,
) -> None:
    """exec_in_container() should return (stdout, stderr, exit_code) tuple."""
    mock_exec_result = MagicMock()
    mock_exec_result.exit_code = 0
    mock_exec_result.output = (b"hello\n", b"")

    mock_container = MagicMock()
    mock_container.exec_run.return_value = mock_exec_result

    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container

    with patch.object(manager, "_docker_client", return_value=mock_client):
        stdout, stderr, exit_code = await manager.exec_in_container(SESSION_ID, "echo hello")

    assert stdout == "hello\n"
    assert stderr == ""
    assert exit_code == 0


@pytest.mark.asyncio()
async def test_exec_returns_error_when_container_missing(
    manager: SandboxManager,
) -> None:
    """exec_in_container() returns exit_code=1 and an error message when container is absent."""
    mock_client = MagicMock()
    mock_client.containers.get.side_effect = docker.errors.NotFound("gone")

    with patch.object(manager, "_docker_client", return_value=mock_client):
        stdout, stderr, exit_code = await manager.exec_in_container(SESSION_ID, "echo hello")

    assert exit_code == 1
    assert SESSION_ID in stderr
