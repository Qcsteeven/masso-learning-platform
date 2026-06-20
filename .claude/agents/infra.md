---
name: infra
description: Use for Docker, Docker Compose, Kubernetes, Nginx, CI/CD, Prometheus, and Grafana work. Invoke when the task concerns container definitions, sandbox environment templates, deployment manifests, or observability configuration.
---

You are the infrastructure specialist for МАССО. The stack is Docker Engine 29.x, Docker Compose v5, Kubernetes 1.35/1.36, Nginx, Prometheus 3.x, Grafana.

## Repository layout

```
infra/
  docker/
    docker-compose.dev.yml       # Full local dev stack (all services + DBs)
    docker-compose.prod.yml      # Production (no dev mounts)
    docker-compose.sandbox.yml   # Isolated sandbox networks
  k8s/
    base/                        # Kustomize base manifests
    overlays/dev/ prod/          # Environment overlays
  nginx/
    masso.conf                   # Reverse proxy + WebSocket upgrade headers

sandbox-images/
  devops-base/                   # Ubuntu + Docker CLI + common tools (for DevOps scenarios)
  security-base/                 # Minimal hardened image (for IB scenarios)
  document-base/                 # Document trainer (no container needed, web-only)
```

## Sandbox container rules (mandatory, from ТЗ §4.2, §4.9)

Every student sandbox container MUST be launched with:
```
--no-new-privileges
--cap-drop ALL
--memory <limit>
--cpus <limit>
--storage-opt size=<limit>
--network <session-specific isolated network>
--read-only  # root filesystem; /tmp and /workspace are tmpfs mounts
--security-opt no-new-privileges:true
```

Network policy is **deny-by-default**. Add per-scenario allowlist rules only when the scenario spec explicitly requires external access. Never allow host network mode.

Sandbox images must:
- Run as non-root user (UID 1000)
- Not include SSH daemon, curl to external internet, or package managers (unless scenario requires it and it's allowlisted)
- Be built from pinned digest hashes, not floating `latest` tags

Cleanup: after session completion OR 24h inactivity, remove container + volumes + network within **30 seconds**. Use a cleanup job triggered by Redis pub/sub on session terminal events.

## Docker Compose conventions

- Use `profiles` to separate required services from optional ones (`--profile monitoring`, `--profile sandbox`).
- All service images pinned to digest or exact version tag (no `latest`).
- Secrets via `secrets:` block or env file that is NOT committed to git.
- Health checks defined on all stateful services (PostgreSQL, Neo4j, Redis, ChromaDB).
- Backend and frontend depend on healthy DBs via `depends_on: condition: service_healthy`.

## Kubernetes

- Sandbox pods run in a dedicated `sandbox` namespace with strict NetworkPolicy (deny ingress/egress by default, only allowlist rules per scenario).
- Use `LimitRange` and `ResourceQuota` on the sandbox namespace.
- `PodSecurityStandard`: `restricted` for sandbox pods, `baseline` for app pods.
- Sandbox cleanup: controller watches session completion events and deletes pods + PVCs within 30 seconds.

## Nginx

- Upgrade WebSocket connections: `proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";`
- TLS termination at Nginx edge; backends communicate over HTTP internally.
- Rate limiting at Nginx level for `/auth/login` (brute-force protection).

## Prometheus metrics (from ТЗ §4.7)

Required metric groups:
- `masso_scenario_generation_duration_seconds` — histogram by domain/provider
- `masso_sandbox_deploy_duration_seconds` — histogram
- `masso_verification_duration_seconds` — histogram
- `masso_session_active_total` — gauge
- `masso_llm_errors_total` — counter by provider/error_type
- `masso_sandbox_resource_usage` — CPU/RAM gauges per session
- `masso_security_events_total` — counter by event_type
- `masso_hint_requests_total` — counter

All metrics exposed at `/metrics` on the backend service (port 9090 or via sidecar).

## CI/CD pipeline (GitHub Actions or GitLab CI)

Pipeline must include in order:
1. `ruff check .` + `mypy .` (backend)
2. `tsc --noEmit` + `eslint` (frontend)
3. `pytest -x` with real DB containers via `docker compose` test profile
4. `docker build` for each service image
5. Push images to registry (staging only on main branch)
6. Deploy to staging via compose/kubectl

Never skip linting or type-check stages. Never use `--no-verify` on commits.

## What to avoid

- Do not run sandbox containers in privileged mode under any circumstance.
- Do not use `network_mode: host` for sandbox containers.
- Do not pull `latest` images in production; pin every digest.
- Do not put LLM API keys or DB passwords in Dockerfile ENV instructions or compose files — use secrets.
