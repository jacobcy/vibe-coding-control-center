# Orchestra Runtime Modes

Orchestra supports two runtime modes for different deployment scenarios.

## Overview

| Mode | Command | Use Case |
|------|---------|----------|
| **Always-on Server** | `vibe3 serve start` | Continuous webhook receiver + heartbeat polling |
| **Periodic Scan** | `vibe3 scan` | Standalone governance/supervisor checks |

Both modes share the same observation logic (OrchestrationFacade) but have different deployment assumptions.

## Always-on Server Mode

**Command**: `vibe3 serve start`

### Characteristics

- Long-running daemon process
- HTTP webhook receiver (FastAPI on port 8080 by default)
- Periodic heartbeat polling (default: 60s interval)
- Event-driven architecture
- FailedGate integration for error recovery

### When to Use

- Production deployments
- Real-time GitHub webhook integration
- Continuous monitoring of issue state changes
- Environments requiring immediate response to webhook events

### Architecture

```
HeartbeatServer (event loop)
  ├── HTTP Server (FastAPI)
  │   └── POST /webhook/github
  └── Polling Loop (heartbeat tick)
      └── OrchestrationFacade
          ├── Governance scan (interval-gated)
          ├── Supervisor scan (interval-gated)
          └── Issue label dispatch polling
```

### Service Lifecycle

- PID file management for daemon control
- Session registry cleanup on startup/shutdown
- FailedGate preflight check before starting
- Graceful shutdown via SIGTERM

### Example

```bash
# Start server with defaults from config/settings.yaml
vibe3 serve start

# Debug mode (60s heartbeat, current branch as base)
vibe3 serve start --debug

# Custom interval and port
vibe3 serve start --interval 30 --port 9000

# Check server status
vibe3 serve status

# Stop server
vibe3 serve stop
```

## Periodic Scan Mode

**Command**: `vibe3 scan [governance|supervisor|all]`

### Characteristics

- Run once and exit
- No HTTP server
- No heartbeat event loop
- Direct event publishing (bypasses interval gating)
- Suitable for cron/scheduled execution

### When to Use

- CI/CD pipeline integration
- GitHub Actions scheduled workflows
- Manual governance checks
- Environments without webhook accessibility
- Testing and debugging specific scan behaviors

### Architecture

```
Scan Command
  └── OrchestrationFacade (direct)
      ├── Governance scan (no interval gating)
      └── Supervisor scan (no interval gating)
```

### Subcommands

#### `vibe3 scan governance [--tick N]`

Runs governance scan once:
- Scans all open issues for governance rule violations
- Publishes `GovernanceScanStarted` event
- Triggers governance agent dispatch via event handler
- Optional `--tick` to override tick count

#### `vibe3 scan supervisor`

Runs supervisor scan once:
- Scans for issues with `supervisor` + `state/handoff` labels
- Publishes `SupervisorIssueIdentified` events
- Triggers supervisor handoff dispatch via event handler

#### `vibe3 scan all [--tick N]`

Runs both governance and supervisor scans in sequence.

### Example

```bash
# Run governance scan
vibe3 scan governance

# Run supervisor scan
vibe3 scan supervisor

# Run both scans
vibe3 scan all

# Dry-run mode (show what would be done)
vibe3 scan governance --dry-run

# Override tick count for governance scan
vibe3 scan governance --tick 42
```

## Shared Components

Both modes share the same core components:

### OrchestrationFacade

Unified entry point for runtime observations:
- Publishes domain events (observation layer)
- Does not execute dispatch directly
- Same observation logic for both modes

### Domain Event Handlers

Event handlers subscribe to domain events:
- `handle_governance_scan_started` - L1 governance chain
- `handle_supervisor_issue_identified` - L2 supervisor chain
- Dispatch execution happens in handlers, not facade

### FailedGate

Error recovery mechanism shared by both modes:
- Blocks dispatch when errors exceed threshold
- SQLite-backed state (shared across modes)
- Manual resume required via `vibe3 serve resume`

### CapacityService

Tracks active execution sessions:
- Prevents over-provisioning
- Same capacity limits for both modes
- Session state persisted in SQLite

## Behavioral Differences

| Aspect | Server Mode | Scan Mode |
|--------|-------------|-----------|
| **Interval gating** | Active (tick modulo check) | Bypassed (explicit request) |
| **Min time between scans** | Enforced | Bypassed |
| **FailedGate check** | Before each tick | Before dispatch |
| **Webhook handling** | Active | Not applicable |
| **PID management** | Required | Not applicable |
| **Session cleanup** | Startup/shutdown | Manual |

## Deployment Recommendations

### Always-on Server

**Production (systemd)**:
```ini
[Unit]
Description=Vibe3 Orchestra Server
After=network.target

[Service]
Type=simple
User=vibe
WorkingDirectory=/opt/vibe3
ExecStart=/usr/local/bin/vibe3 serve start --no-async
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

**Development (tmux)**:
```bash
vibe3 serve start  # Default: async tmux session
vibe3 serve start --no-async  # Foreground (blocking)
```

### Periodic Scan

**Cron (every 5 minutes)**:
```cron
*/5 * * * * cd /opt/vibe3 && vibe3 scan all >> /var/log/vibe3/scan.log 2>&1
```

**GitHub Actions (scheduled workflow)**:
```yaml
name: Orchestra Governance Scan
on:
  schedule:
    - cron: '*/5 * * * *'  # Every 5 minutes
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install vibe3
        run: pip install -e .
      - name: Run governance scan
        run: vibe3 scan governance
```

**Manual debugging**:
```bash
# Test governance scan without execution
vibe3 scan governance --dry-run

# Run with verbose logging
vibe3 scan all -vv
```

## Risk Mitigation

### Duplicate Execution

If both modes run simultaneously:
- **Session registry check** prevents duplicate governance runs
- Same SQLite session state prevents concurrent dispatch
- CapacityService enforces max_concurrent_flows limit

### FailedGate State Sharing

- Both modes use same SQLite store for FailedGate
- Scan command respects FailedGate state
- Manual resume required: `vibe3 serve resume --reason "<reason>"`

### Service Initialization

- Both modes use same service factories
- SQLiteClient, CapacityService, FailedGate initialized identically
- Event handlers registered before publishing events

## Configuration

Both modes share the same configuration in `config/settings.yaml`:

```yaml
orchestra:
  enabled: true
  repo: "owner/repo"
  port: 8080
  polling_interval: 60
  max_concurrent_flows: 5

  governance:
    interval_ticks: 1  # Scan every tick (server mode)
    enabled: true

  supervisor_handoff:
    interval_ticks: 1  # Scan every tick (server mode)
    enabled: true
```

**Note**: `interval_ticks` only applies to server mode. Scan mode bypasses interval gating.
