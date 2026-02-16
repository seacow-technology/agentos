# Agent Execution Rules (Repo Local)

## Hard Constraints

1. **Do not manually edit anything under `publish/webui-v2/`.**
2. `publish/webui-v2/` is **release-script-controlled generated output**.
3. Any WebUI source change must be made in the editable source tree (for example `apps/webui/`) and then propagated by the official publish/release generation flow.
4. If a requested change appears to require directly touching `publish/webui-v2/`, stop and redirect to source-side change + generation step instead of editing generated files.

---

## Release Memory (Repo Map + Workflow)

This section is the "single source of truth" for how release/sync is expected to work across the multiple repos checked out under `/Users/pangge/PycharmProjects/AgentOS`.

### Repo Map (Local Path -> GitHub Repo -> Role)

- `/Users/pangge/PycharmProjects/AgentOS` -> `octopusos/octopusos-origin` (private)
  - Main dev/product repo. Semver comes from `VERSION` (e.g. `3.4.0`) and tags are `vX.Y.Z`.
  - Has `public` remote -> `octopusos/octopusos` and release/export scripts under `scripts/publish/`.
- `/Users/pangge/PycharmProjects/AgentOS/publish` -> `octopusos/octopusos` (public)
  - Public mirror. Updated by running the official export/sync flow from the private repo (do not hand-edit generated outputs).
- `/Users/pangge/PycharmProjects/AgentOS/octopusos-runtime` -> `octopusos/octopusos-runtime`
  - Desktop sidecars artifacts repo. Contains `manifest.json` and per-tag `artifacts/vX.Y.Z/*`.
  - Published by the private repo script `scripts/desktop/publish_runtime_repo.sh`.
- `/Users/pangge/PycharmProjects/AgentOS/homebrew/octoctl-cli` -> `octopusos/octoctl`
  - CLI repo. Tag push `vX.Y.Z` triggers GitHub Actions to build:
    - `octoctl-vX.Y.Z-darwin-{arm64,amd64}`
    - `octopus-manager-vX.Y.Z-darwin-{arm64,amd64}` (built from `octopusos/octopusos` at the same tag if it exists; else falls back to `main`)
  - Homebrew tap update should ultimately point at the release assets of this repo.
- `/Users/pangge/PycharmProjects/AgentOS/homebrew/octoctl` -> `octopusos/homebrew-octoctl`
  - Homebrew tap. `Formula/octoctl.rb` pins `version`, URLs, and sha256 for both `octoctl` and `octopus-manager`.
- `/Users/pangge/PycharmProjects/AgentOS/extensions` -> `octopusos/octopusos-extensions`
  - Extensions snapshot repo (tagged to align with product releases).
- `/Users/pangge/PycharmProjects/AgentOS/skills` -> `octopusos/octopusos-skills`
  - Skills snapshot repo (tagged to align with product releases).
- `/Users/pangge/PycharmProjects/AgentOS/libraries` -> `octopusos/octopusos-libraries`
  - Shared libs snapshot repo (tagged to align with product releases).

### Release / Sync Rules Of Thumb

- Versions are semver `X.Y.Z`; tag format is `vX.Y.Z`.
- Public repo updates must go through the scripted export/sync flow:
  - start in private repo (`octopusos-origin`) -> `./scripts/publish/release.sh ...` -> PR in `publish/` -> merge -> then tag/release in public repo.
- Avoid "manual git pushes" for public sync; follow the gates documented in `scripts/publish/SCRIPTS_USAGE.md`.
- Tag rewriting is risky. Preferred strategy when a tag points to the wrong commit:
  - if already consumed externally, publish a new patch version (`vX.Y.(Z+1)`) instead of force-moving the tag
  - only force-move a tag when you explicitly choose that strategy and accept the implications

### Per-Repo Execution Checklist (vX.Y.Z)

1. Private product (`octopusos-origin`)
   - bump `VERSION`
   - build/test as required
   - tag + GitHub Release (assets as needed)
2. Public product (`octopusos/octopusos`, via `publish/`)
   - run scripted export/sync, merge PR to `main`
   - tag + GitHub Release
3. Runtime sidecars (`octopusos-runtime`)
   - run `./scripts/desktop/publish_runtime_repo.sh` on each target platform (darwin-arm64, darwin-amd64, windows-x64, linux-x64, etc.)
   - verify `octopusos-runtime/manifest.json` points at `vX.Y.Z` and release has the binaries
   - note: the script also touches `apps/desktop-electron/assets/sidecars-manifest.json` in the private repo; decide whether to keep that change (commit) or discard it
4. octoctl (`octopusos/octoctl`)
   - set `homebrew/octoctl-cli/pyproject.toml` version to `X.Y.Z`
   - push tag `vX.Y.Z` to trigger CI release build
   - ensure public product repo already has the same tag `vX.Y.Z` so `octopus-manager` builds from a consistent product snapshot
5. Homebrew tap (`homebrew-octoctl`)
   - update `Formula/octoctl.rb` to `version "X.Y.Z"` + URLs to `octopusos/octoctl` release assets + sha256
6. extensions/skills/libraries
   - tag `vX.Y.Z` (and optionally create a lightweight GitHub Release as a snapshot marker)
