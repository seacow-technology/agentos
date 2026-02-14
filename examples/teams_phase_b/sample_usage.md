# Teams Phase B Sample Usage

1. Configure environment variables:
   - `OCTOPUSOS_TEAMS_OAUTH_CLIENT_ID`
   - `OCTOPUSOS_TEAMS_OAUTH_CLIENT_SECRET`
   - `OCTOPUSOS_TEAMS_OAUTH_REDIRECT_URI`
   - `OCTOPUSOS_TEAMS_GLOBAL_BOT_ID`
   - `OCTOPUSOS_TEAMS_APP_ID`
2. Open WebUI: `/channels/teams`.
3. Click `Connect organization`.
4. After callback, check:
   - `GET /api/channels/teams/orgs`
   - `GET /api/channels/teams/{tenant_id}/evidence`
5. Manual reconcile if needed:
   - `POST /api/channels/teams/{tenant_id}/reconcile`
