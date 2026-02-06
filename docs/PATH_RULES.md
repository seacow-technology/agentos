# PATH_RULES

## Goal
After installation, users can run `octopusos` directly from any shell without running repair commands.

## Rules
- Prefer installer-managed Machine PATH updates for Windows (requires UAC)
- If Machine PATH update is denied by policy, fallback to User PATH and show a clear message
- If shell refresh is required, installer must present an explicit prompt
- User-space fallback path must be deterministic and documented

## Post-Install Validation
- New PowerShell session: `Get-Command octopusos` resolves
- `octopusos --version` returns expected version
