# Task: C_DESKTOP_004

- title: Commercial Scenario: Product tasks list + plan/evidence/replay modals render and downloads work
- portal: desktop
- bucket: commercial/task_replay_evidence

## Context
- plan: /Users/pangge/PycharmProjects/AgentOS/frontend/reports/commercial_scenario_plan.md

## Scope
From Product Shell Tasks tab: open Plan/Evidence/Replay for a task, verify modal renders, and download URLs are reachable (200) when present.

## Hard Constraints
- Do not invent endpoints; use only repo evidence.
- If backend gap is confirmed, disable UI action with clear message and mark BLOCKED with evidence.
- Do not change auth flows, CI workflows, or mass-format.
- Do not manually edit anything under publish/webui-v2/.

## Acceptance
Evidence includes: GET /api/product/tasks, GET /api/product/tasks/{id}/plan, GET /api/product/tasks/{id}/evidence, GET /api/product/tasks/{id}/replay, and any /download/* responses. Store in frontend/reports/e2e_endpoint_evidence/C_DESKTOP_004.json.

## Hints / Known Gaps
Backend lives in os/octopusos/webui/api/product.py.
