# Task: C_DESKTOP_002

- title: Commercial Scenario: AWS Ops page creates a chat session with aws context and hands off to Chat
- portal: desktop
- bucket: commercial/aws_ops

## Context
- plan: /Users/pangge/PycharmProjects/AgentOS/frontend/reports/commercial_scenario_plan.md

## Scope
On /aws: profiles list loads; region required; quick action creates session, posts first message, navigates to /chat and focuses the session.

## Hard Constraints
- Do not invent endpoints; use only repo evidence.
- If backend gap is confirmed, disable UI action with clear message and mark BLOCKED with evidence.
- Do not change auth flows, CI workflows, or mass-format.
- Do not manually edit anything under publish/webui-v2/.

## Acceptance
Evidence includes: GET /api/mcp/aws/profiles result, POST /api/sessions result, POST /api/sessions/{id}/messages result. Store in frontend/reports/e2e_endpoint_evidence/C_DESKTOP_002.json.

## Hints / Known Gaps
WebUI page is apps/webui/src/pages/AwsOpsPage.tsx.
