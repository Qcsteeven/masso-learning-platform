---
description: Audit the Docker sandbox security posture for МАССО student containers. Use when asked to verify sandbox security, before a security review, or after changing container launch code.
---

Audit the security posture of МАССО sandbox containers.

## Check running sandbox containers

```bash
# List all student sandbox containers
docker ps --filter "label=masso.role=sandbox" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}"

# For each container ID, inspect security settings:
CONTAINER_ID=<id>

docker inspect $CONTAINER_ID | jq '{
  no_new_privileges: .HostConfig.SecurityOpt,
  cap_add: .HostConfig.CapAdd,
  cap_drop: .HostConfig.CapDrop,
  privileged: .HostConfig.Privileged,
  network_mode: .HostConfig.NetworkMode,
  pid_mode: .HostConfig.PidMode,
  memory: .HostConfig.Memory,
  cpus: .HostConfig.NanoCpus,
  readonly_rootfs: .HostConfig.ReadonlyRootfs
}'
```

## Required values (all must be true)

- `Privileged`: **false**
- `CapDrop`: contains **"ALL"**
- `CapAdd`: **null or empty** (no capabilities re-added unless scenario explicitly requires it)
- `SecurityOpt`: contains **"no-new-privileges:true"**
- `ReadonlyRootfs`: **true**
- `NetworkMode`: must be a **named isolated network** (not `host`, not `bridge`)
- `Memory`: non-zero (≤ sandbox profile limit)
- `NanoCpus`: non-zero (≤ sandbox profile limit)

## Check network isolation

```bash
# Inspect the container's network
docker inspect $CONTAINER_ID | jq '.NetworkSettings.Networks | keys'

# Verify it's NOT the default bridge or host
# Each session should have its own network: masso-session-{session_id}
docker network inspect masso-session-<session_id> | jq '{
  driver: .[0].Driver,
  internal: .[0].Internal,
  options: .[0].Options
}'
# Internal: true means no external routing
```

## Check for privilege escalation risks

```bash
# Check for setuid binaries in the container (run inside the container)
docker exec $CONTAINER_ID find / -perm -4000 -type f 2>/dev/null

# Check running processes
docker exec $CONTAINER_ID ps aux

# Verify non-root user
docker exec $CONTAINER_ID id
# Expected: uid=1000 (not 0)
```

## What to report

For each checked container:
- List any FAILED checks with the actual value vs. expected value
- Flag any setuid binaries found
- Flag if any container is running as root (uid=0)
- Flag if network_mode is host or bridge

If all checks pass, confirm explicitly that all mandatory security flags are in place.
