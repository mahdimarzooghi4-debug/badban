# Sprint 75 — Isolated Keycloak Stage readiness (Draft)

- **Status:** Code + infrastructure plan candidate; no Render Blueprint approval, deployment, or Stage admission.
- **Owner decision:** Use self-hosted Keycloak as Badban's central OIDC identity provider; keep SMS OTP and Shahkar integration slots **UNCONFIGURED**.
- **Target:** GitHub `main` SHA `6e3c5a482dc0401c3e27a129f174e76fcda3a9f4` as the existing application baseline.
- **Limit:** The identity runtime must not be mistaken for a fully integrated or Stage-approved Badban deployment.

## Delivered in this Draft

- An **opt-in** separate file `render-keycloak-stage.yaml`. It is not `render.yaml` and does not affect existing deployments.
- A version-pinned Keycloak **26.8.2** production-mode Docker build (not `start-dev`).
- A Render entrypoint that requires a private PostgreSQL URL, separately supplied database username/password, and a secure bootstrap administrator password. Missing inputs stop startup.
- A distinct `badban-keycloak-stage-db` database with `ipAllowList: []`, not the pre-existing `badban-stage-db`.
- A Render-generated administrator secret (not embedded in Git or chat).
- Render TLS hostname derived from the actual assigned `RENDER_EXTERNAL_HOSTNAME`, using production-mode Keycloak behind the edge proxy.
- Manual deployment only; no auto-deploy from Git.
- Repository tests ensure these boundaries survive code changes.

## Deployment-cost gate

Per official Keycloak container guidance, memory limits should be at least ~750 MB and small operational deployments commonly require 2 GB. Render Free and Starter web services have 512 MB. Therefore this Blueprint proposes a **Standard / 1 CPU / 2 GB web service** (paid, currently listed at approximately **USD 25/month**, before extras) instead of silently using a fragile or insecure 512 MB runtime. Its **separate Free Postgres** is ephemeral, expires in 30 days, and has no managed backup: use synthetic sandbox identity data only, never real user identity information. Confirm pricing in Render's actual plan before explicit owner approval.

**Planning is not approval**: create/plan the Blueprint, show the exact resource changes and cost, and obtain explicit owner authorization before `approve_blueprint`, service creation or paid billing.

## Required readiness checks before actually running the service

1. Plan validation succeeds and lists only new Keycloak Stage Web + Keycloak-specific Postgres resources, never changes existing Badban resources.
2. Approved Stage administrator must rotate/recover bootstrap credentials via restricted Render Dashboard access, enable MFA for privileged users, and avoid test accounts with real national IDs.
3. Protect admin UI and review allowed network entry points/proxy header trust. A public admin console is not automatically safe merely because TLS terminates at Render.
4. Before OIDC activation, explicitly configure and verify a realm, public web client, exact `/auth/callback` redirect, allowed origins, trusted issuer/audience and exact `national_id` claim semantics.
5. Never create a verified national-ID claim from phone ownership. Real identity proofing, SMS/OTP factor and Shahkar matching remain unavailable, per Decision 0079.
6. Don't set `BADBAN_OIDC_ISSUER` or enable the Badban API with fabricated settings. The current Badban Stage runtime remains blocked until the separate Vault client, NATS, worker, DB migration and security/recovery checks exist.
7. Before Stage acceptance, perform HTTPS/discovery/JWKS validation, denial for missing claim, user/role isolation, token expiry/revocation, browser PKCE and recovery rehearsal.

## Exclusions

- No Keycloak realm/client/user created. No test identities are fabricated and no real users are enrolled.
- No OTP provider, SMS message, Shahkar API, private key or token is invented.
- No Badban authorization, national identity, finance, ledger or transaction state is changed.
- No Stage admission, QA, Production, or payment transaction is permitted.
- Don't merge this Draft PR without Code Review and explicit owner approval.

References: official Keycloak container/reverse-proxy guides and Render Blueprint/plan documentation.
