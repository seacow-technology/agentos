# publish/ - OctopusOS Packaging and Distribution

This directory is the single source of truth for building, packaging, signing, and validating OctopusOS distributable artifacts across Windows, macOS, and Linux.

## Scope
- Build and release automation
- Installers and package assets
- Artifact naming and versioning rules
- Signing and notarization policy
- CI pipeline wiring for publishing
- Product-level smoke tests against built artifacts

## Out of Scope
- Core runtime logic (lives in `os/octopusos/`)
- Desktop tray source (lives in `apps/desktop/`)
- WebUI product code (lives in `apps/webui/` or `os/octopusos/webui/`)

## Artifact Types
1. CLI + daemon runtime (`octopusos` command)
2. Desktop controller app (tray/menubar)
3. Installers and platform packages

## Naming Convention
`octopusos-<component>-<version>-<os>-<arch>[-<channel>].<ext>`

Examples:
- `octopusos-cli-2.1.0-windows-x86_64-stable.zip`
- `octopusos-desktop-2.1.0-macos-arm64-stable.dmg`
- `octopusos-installer-2.1.0-windows-x86_64-stable.msi`

## Version Source
Use `pyproject.toml` `[project].version` as single source for artifact version.

## Output Layout
All outputs must go under `publish/artifacts/`:

- `publish/artifacts/manifests/manifest.json`
- `publish/artifacts/manifests/checksums.sha256`
- `publish/artifacts/windows/`
- `publish/artifacts/macos/`
- `publish/artifacts/linux/`

## Build Entry Points
- `publish/scripts/package_all.sh`
- `publish/scripts/build_cli.sh`
- `publish/scripts/build_desktop.sh`
- `publish/scripts/build_windows.ps1`
- `publish/scripts/smoke_test.sh`

## Acceptance Gates
See:
- `publish/docs/TEST_MATRIX.md`
- `publish/docs/RELEASE_CHECKLIST.md`
- `tests/publish/`

## Open Source Boundary
`publish/src/` is treated as a standalone public boundary.
Code in `publish/src/` must not import from private runtime modules under `os/octopusos/`.

## Branding Rule
All user-facing packaging output must use `OctopusOS`.
Do not introduce new `AgentOS` strings in artifact names, install paths, or installer UI.
