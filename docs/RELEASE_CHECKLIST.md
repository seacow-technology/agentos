# RELEASE_CHECKLIST

## Preflight
- [ ] Version source is synchronized from `pyproject.toml`
- [ ] Required OS/arch artifacts were generated
- [ ] `manifest.json` and `checksums.sha256` generated

## Validation
- [ ] `tests/publish/` test suite passed
- [ ] Smoke tests passed on target platforms
- [ ] `octopusos webui start|status|stop` lifecycle validated
- [ ] Port conflict behavior validated

## Windows Post-Install Smoke (Required)
- [ ] `octopusos --version` returns non-empty version
- [ ] `octopusos doctor` prints `Data dir`/`Log file`/`Status file` and paths are writable
- [ ] `octopusos webui start` exits with code 0
- [ ] `octopusos webui status` shows running and URL
- [ ] `octopusos logs --tail --lines 5` returns output consistently
- [ ] Running `octopusos webui start` again returns idempotent `already running`
- [ ] `octopusos webui stop` stops daemon successfully
- [ ] `octopusos webui status` after stop shows not running
- [ ] Default port conflict triggers fallback behavior and status reflects fallback (`port_source` and/or new bound port)
- [ ] Control API `GET /api/daemon/status` is reachable with token and returns `running/pid/port/url`

## Windows Evidence Bundle (M3.3 Required)
- [ ] `publish/artifacts/<version>/windows/evidence/` is uploaded on every workflow run (`always()`)
- [ ] Evidence contains `install.log` / `uninstall.log` / `doctor.txt` / `smoke_transcript.txt`
- [ ] Evidence contains `ports.txt` and `status_fallback.json` (always), plus `daemon_status.json` when daemon/token are available
- [ ] Evidence contains runtime logs under `evidence/logs/`

## Signing and Compliance
- [ ] Windows artifacts signed (or explicitly marked unsigned)
- [ ] macOS artifacts notarized if distributed outside Homebrew
- [ ] Security review confirms local-only control channel

## Publishing
- [ ] Release notes include behavior changes and known limits
- [ ] Artifact links and checksums published
- [ ] Rollback instructions validated

## External Demo Readiness
- [ ] `manifest.json` is present and shows `full_version` / `msi_version` / `channel`
- [ ] `smoke_transcript.txt` shows full PASS flow (including port fallback and control API checks)
- [ ] Status evidence is present via `daemon_status.json` (preferred) or `status_fallback.json`
- [ ] `install.log` confirms MSI install and PATH wiring behavior
