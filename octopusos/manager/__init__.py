"""OctopusOS Desktop Control Manager (local-only).

This package provides a small local Control API that can start/stop/restart
the WebUI backend daemon (and optionally the WebUI frontend dev server).

Design goal: a single, local "process housekeeper" that tray/CLI/Web can
talk to without each client spawning processes independently.
"""

