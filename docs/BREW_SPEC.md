# BREW_SPEC

## Targets
- macOS (required)
- Linux Homebrew (recommended)

## Formula Requirements
- Installs `octopusos` executable into Homebrew bin path
- Avoids requiring `uv run` at runtime
- Post-install message includes `octopusos webui start` quick check

## Validation
- Fresh shell command availability
- `octopusos webui start|status|stop` verified after install
