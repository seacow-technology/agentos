# Task: C_DESKTOP_003

- title: Commercial Scenario: Projects CRUD in embedded Console works end-to-end (read-only safe path first)
- portal: desktop
- bucket: commercial/projects

## Context
- plan: /Users/pangge/PycharmProjects/AgentOS/frontend/reports/commercial_scenario_plan.md

## Scope
Open /projects in embedded mode and ensure list loads. If create requires admin token, UI must prompt clearly and not crash. Prefer exercising list + view flows first.

## Hard Constraints
- Do not invent endpoints; use only repo evidence.
- If backend gap is confirmed, disable UI action with clear message and mark BLOCKED with evidence.
- Do not change auth flows, CI workflows, or mass-format.
- Do not manually edit anything under publish/webui-v2/.

## Acceptance
Evidence includes: GET /api/projects response (200) and any subsequent 4xx/5xx. Store in frontend/reports/e2e_endpoint_evidence/C_DESKTOP_003.json.

## Hints / Known Gaps
ProjectsPage uses octopusosService.listProjectsApiProjectsGet.
