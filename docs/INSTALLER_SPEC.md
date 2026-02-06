# INSTALLER_SPEC

## Windows
- Installer type: MSI or EXE bootstrapper
- Runtime strategy: bundled runtime, no dependency on system Python/uv/node
- Install location (default): `C:\Program Files\OctopusOS\` (machine install)
- Data location (runtime): `%LOCALAPPDATA%\OctopusOS\`
- PATH behavior: `octopusos` command available in a new shell after install
- MSI versioning: MSI `Version` uses numeric `MAJOR.MINOR.PATCH`; full OctopusOS version (including suffixes like `-beta`/`+sha`) is preserved in installer metadata/manifest

## PATH Rule
- Prefer Machine PATH update for product-like experience (UAC expected)
- If policy blocks Machine PATH, fallback to User PATH with explicit installer message

## Uninstall
- Remove installed binaries and PATH entry
- Keep runtime data under `%LOCALAPPDATA%\OctopusOS\` unless user selects purge

## Upgrade
- In-place upgrade should preserve runtime data and logs
- Existing daemon should stop/restart cleanly during upgrade

## Security
- Installer must only expose local control path to daemon APIs
- Any control token material stored in user data directory with user-only permissions where supported
