# OctopusOS Evidence Bundle (Windows MSI CI)

This document defines the **Evidence Bundle** produced by the Windows MSI pipeline.
The bundle is designed for:
- deterministic troubleshooting (no guesswork),
- reproducible incident analysis,
- enterprise-grade auditability,
- demo-ready proof of installation & runtime behavior.

> Principle:
> Evidence is the source of truth. If it isn't in the bundle, it didn't happen.

---

## 1. Location & Structure

The evidence bundle is generated on every Windows CI run (success or failure) and placed under:

`publish/artifacts/<version>/windows/evidence/`

The canonical schema is defined in:

`publish/docs/evidence_schema.json`

CI output, this document, and tests must stay aligned to that schema.

Expected structure:

```text
evidence/
smoke_transcript.txt
smoke-installed.log
install.log
uninstall.log
doctor.txt
daemon_status.json
status_fallback.json
ports.txt
logs/
  *.log
  ...
manifest.json
checksums.sha256
```

Notes:
- `daemon_status.json` is optional and is generated only when control API + token are reachable.
- `status_fallback.json` is always generated and provides deterministic status evidence when `daemon_status.json` is unavailable.
- The pipeline must upload evidence artifacts using `always()` semantics.

---

## 2. File Index & Semantics

### 2.1 `smoke_transcript.txt` (Primary Narrative)
**Purpose:** Human-readable, step-by-step record of the post-install smoke test.

Contains:
- `[STEP]` markers for each check
- `[PASS]` / `[FAIL]` outcomes
- every `octopusos ...` command executed in a clean PowerShell child process
- command output (stdout/stderr)
- port conflict decision trail: `blocked_port`, `port_decision ...`

How to read:
- Search for the first `[FAIL]` to find the failure boundary.
- Immediately above the failure, locate the last successful `[PASS]` step.
- Use referenced paths (`log_path`, `data_dir`, `status_path`) to jump to the correct diagnostics.

Common failure signatures:
- `octopusos: not recognized` -> PATH wiring issue / installer did not update Machine PATH
- `webui start` succeeds but `status` shows stopped -> daemon lifecycle or process signature mismatch
- `token` / `X-OctopusOS-Token` errors -> token path/permissions or wrong status URL

---

### 2.2 `smoke-installed.log`
**Purpose:** Raw console log for the smoke execution step (pipeline log capture).
Used when transcript parsing is insufficient or to cross-check missing stdout.

---

### 2.3 `install.log` / `uninstall.log` (MSI Logs)
**Purpose:** Definitive MSI-level trace from `msiexec`.

Contains:
- component installation actions,
- registry/environment writes (including PATH),
- rollback behavior,
- error codes and action-level failures.

How to read:
- Search for `Return value 3` to locate the MSI failure region.
- Identify which action failed (e.g., component install, environment update).
- Confirm `Program Files\\OctopusOS` target directory and PATH write succeeded.

---

### 2.4 `doctor.txt` (Post-install Runtime Snapshot)
**Purpose:** A consistent runtime self-check output used for both CI and support.

Should include (minimum):
- OctopusOS version / channel
- data_dir
- log_path
- status_path
- daemon state summary
- recent error excerpt (if present)

How to read:
- Confirm paths match expectations (Windows `%LOCALAPPDATA%\\OctopusOS` for data/logs).
- Use `log_path` to jump into `evidence/logs/`.

---

### 2.5 `daemon_status.json` (Control Plane Proof)
**Purpose:** Machine-readable proof that the local control plane is reachable.

Expected fields (example):
- `running` (bool)
- `pid` (int)
- `port` (int)
- `url` (string)
- `port_source` (string)
- `data_dir` (string)
- `log_path` (string)
- `status_path` (string)

How to read:
- If missing: daemon likely never started, token could not be read, or status URL unreachable.
- If `running=false` but install succeeded: focus on daemon start + process signature check.

---

### 2.5b `status_fallback.json` (Guaranteed Status Record)
**Purpose:** Always-present status artifact for demo/readiness and failure triage.

Expected fields:
- `running` (bool or null)
- `source` (`control_api` or `fallback`)
- `reason` (string, for fallback path)
- `timestamp` (ISO string)

How to read:
- If `source=control_api`, this mirrors control plane reachability.
- If `source=fallback`, use `reason` and `doctor.txt`/`logs/` to continue triage.

---

### 2.6 `ports.txt` (Port Conflict Trail)
**Purpose:** A short, structured trace for port selection and fallback logic.

Should record:
- default/configured port
- `blocked_port` (if we simulated conflict)
- chosen fallback port
- `port_source` (configured / fallback / random / env / etc.)

How to read:
- Validate port fallback logic matches `smoke_transcript.txt` and `daemon_status.json`.

---

### 2.7 `logs/` (Runtime Logs)
**Purpose:** Canonical daemon/webui runtime logs copied from the OctopusOS data_dir.

Expect:
- daemon lifecycle logs
- webui logs
- error traces that correlate with smoke failure points

How to read:
- Search timestamps around the `[FAIL]` step in `smoke_transcript.txt`.
- Confirm whether process start succeeded, bound port was correct, and control API token gating worked.

---

### 2.8 `manifest.json` & `checksums.sha256`
**Purpose:** Artifact identity, reproducibility, and verification.

`manifest.json` should include:
- `full_version` (e.g., `1.4.2-beta+sha...`)
- `msi_version` (e.g., `1.4.2`)
- `channel`
- `build_sha`
- artifact filenames and hashes (optional)

`checksums.sha256` should include:
- MSI checksum (required)
- optional: evidence bundle checksum

---

## 3. Triage Playbook (Fast Paths)

### 3.1 Installation Fails
1. Open `install.log` -> search `Return value 3`
2. Identify failing action
3. Check `Program Files\\OctopusOS` permission and PATH write actions
4. Verify evidence still includes `doctor.txt` (if not present, install failed before runtime steps)

### 3.2 CLI Not Found After Install (PATH)
1. Open `smoke_transcript.txt`
2. Look for `octopusos: not recognized`
3. Confirm installer wrote Machine PATH (check `install.log`)
4. Confirm smoke executed in a new PowerShell process (expected behavior)

### 3.3 WebUI Start Succeeds but Status/URL Wrong
1. Check `daemon_status.json` (if present)
2. Check `ports.txt` for fallback decision
3. Check `logs/` for bind failure or stale pid cleanup

### 3.4 Control API Fails (Token / Loopback)
1. Confirm token path in `doctor.txt`
2. Confirm `daemon_status.json` was generated (if missing, token read or URL fetch failed)
3. Check runtime logs for token gating failures or binding issues

### 3.5 Stop/Uninstall Leaves Residue
1. Confirm `uninstall.log` completes successfully
2. Confirm `octopusos` not found in new PowerShell (optional check)
3. Data directory retention is **by design** unless explicitly configured otherwise

---

## 4. Demo Script (What to Show Externally)

For demos, show evidence in this order:
1. `manifest.json` - version identity (full vs MSI version), channel, sha
2. `smoke_transcript.txt` - PASS sequence, port fallback, control plane check
3. `daemon_status.json` (or `status_fallback.json`) - proof of status outcome
4. `install.log` - proof of MSI-level install and PATH wiring
5. `logs/` - proof of runtime observability and auditability

Talking points:
- "OctopusOS ships with a reproducible install pipeline."
- "We can prove every runtime decision with auditable evidence."
- "Failures are diagnosable without access to the user's machine."

---

## 5. Guarantees & Non-goals

Guarantees:
- Evidence is produced on every CI run via `always()`.
- Evidence format is stable (breaking changes require doc + version bump).
- Troubleshooting does not require guessing.

Non-goals (for now):
- Video recording (optional, manual-trigger only)
- Full remote telemetry (local-first product; evidence is local/CI artifact)

---

## 6. Change Control

Any changes to evidence schema must:
- update this document,
- update the CI artifact generation,
- update `tests/publish` assertions accordingly.
