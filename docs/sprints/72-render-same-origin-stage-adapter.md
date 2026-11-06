# Sprint 72 — Same-origin Render Stage web/API adapter

**Status:** Code candidate stacked on Draft PR #83; no merge, Stage admission or Render deployment.

## Delivered
- Opt-in FastAPI static adapter: only `/`, `/app`, `/auth/callback`, `/assets/*` and `/runtime-config.js`; all `/api/v1/*` continue through the existing authenticated FastAPI routes.
- Runtime OIDC metadata contains only the public issuer and client ID. Browser access tokens remain in memory, PKCE is unchanged, no client secret is written to JavaScript or browser storage.
- Strict startup refusal if the configured static build is absent/incomplete or if a public OIDC client ID is missing. API-only deployments remain unchanged.
- Security response headers including CSP, no-store, nosniff, no-referrer, and frame denial on the HTML entrypoints.
- The combined Docker image defaults to `BADBAN_APP_ENV=stage` and `BADBAN_SECRET_PROVIDER=vault`; missing real Stage dependencies or approved secrets must prevent startup, not silently fall back to development.\n- Separate multi-stage `Dockerfile.render-stage` builds the React bundle into the FastAPI image. The old backend-only Dockerfile is unchanged. The Web CI builds this combined image, **but does not deploy it**.
- Negative tests verify that the adapter cannot shadow backend API routes, that Stage's Vault restriction is preserved, and that runtime configuration rejects unsafe issuers.

## Still blocking a real Render Stage
1. **Actual Vault** — the accepted secret-provider contract mandates Vault for `app_env=stage`, but its runtime implementation is missing. No environment-secret fallback is permitted. This adapter deliberately leaves that check intact.
2. **Real IdP** — an approved HTTPS OIDC issuer and public client with exact `/auth/callback` redirect URI must be provisioned and verified. Do not invent credentials or a fake issuer.
3. **Dedicated dependencies** — PostgreSQL, NATS JetStream, worker process, audit/metrics, backup and restore exercises must be provisioned and verified, with tenant isolation and relevant deployment security.
4. **Release candidate** — the new UI and API changes are still in stacked Draft PRs, not reviewed and merged into `main`. Stage needs a selected merged SHA under Decision 0033.
5. **Browser/operational gates** — actual IdP-backed browser E2E, HTTPS/browser security testing, visual parity, migrations and recovery, load and observability evidence remain open.

## Future Render inputs (not executed)
When authorized, set Dockerfile path `Dockerfile.render-stage`, auto-deploy off and select an approved **main** release candidate. The combined runtime requires `BADBAN_WEB_OIDC_CLIENT_ID` (public OIDC client), `BADBAN_OIDC_ISSUER` (trusted HTTPS issuer), and `BADBAN_WEB_DIST_DIR=/app/web-dist` (from image). It also requires the existing approved backend settings and real Vault before Stage can start. None of the environment values, credentials, backend services or billing have been provisioned in this Sprint.

**No merge, Render service, database, funding/transfer activity or Production release is performed.**
