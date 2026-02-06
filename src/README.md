# publish/src

This directory is the open-source boundary for packaging-facing code.

## Contract
- `publish/src/` must be able to stand alone as a public repository.
- Code here must not import private runtime internals from `os/octopusos/` or `apps/desktop/`.
- Public interaction must use released artifact contracts (CLI flags, installer interfaces, and documented local control API).

## Scope
- Installer bootstrap helpers
- CLI shims and launch wrappers
- Platform detection and PATH setup helpers
- Distribution tooling that is runtime-agnostic

## Stability Note
This directory contains production-used open-source code, but API stability is not guaranteed unless explicitly versioned.
