# TEST_MATRIX

## 1) Platform and Architecture
| OS | Version | Arch | Coverage |
|---|---|---|---|
| Windows | 11 | x86_64 | Required |
| macOS | 14+ | arm64 | Required |
| Ubuntu | 22.04/24.04 | x86_64 | Required |
| macOS | 14+ | x86_64 | Recommended |
| Ubuntu | 22.04/24.04 | arm64 | Optional |

## 2) Permission Matrix
| Scenario | Expected |
|---|---|
| Standard user install | Clear UAC/sudo prompt or user-space fallback |
| Admin install | PATH and runtime registration available immediately |
| Restricted PATH environment | Clear fallback or explicit failure reason |

## 3) Port Conflict Matrix
| Scenario | Operation | Expected |
|---|---|---|
| Default port free | `octopusos webui start` | Start succeeds, status records selected port |
| Default port occupied | `octopusos webui start` | Switch to fallback port and record in status/log |
| Race during bind | `octopusos webui start` | Fails fast with explicit log and status reason |

## 4) Lifecycle Matrix
| Scenario | Operation | Expected |
|---|---|---|
| Not running | `start` | daemon starts |
| Already running | `start` | idempotent `already running` response |
| Running | `stop` | graceful stop and pid cleanup |
| Not running | `stop` | `not running` response |
| Stale pid/state | `status` or `start` | stale state detected and corrected |

## 5) Tray/Menubar Matrix
| Scenario | Operation | Expected |
|---|---|---|
| daemon down | Tray Start | daemon starts and UI refreshes |
| daemon up | Tray Stop | daemon stops and UI refreshes |
| logs | View Logs | opens correct log path or embedded viewer |
| tray quit | Quit | tray exits, daemon remains unless user stopped it |

## 6) Install/Uninstall/Upgrade
| Scenario | Expected |
|---|---|
| Fresh install | `octopusos webui start` works in a new shell |
| Uninstall | command removed; data retention follows documented policy |
| Upgrade install | config and logs retained; daemon restart succeeds |
