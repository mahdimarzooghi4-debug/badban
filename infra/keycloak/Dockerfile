# Isolated Stage identity candidate. No local dev mode or embedded credentials.
# Version pinned to the Keycloak 26.8.2 security-fix release.
FROM quay.io/keycloak/keycloak:26.8.2 AS builder
ENV KC_DB=postgres \
    KC_HEALTH_ENABLED=true
RUN /opt/keycloak/bin/kc.sh build

FROM quay.io/keycloak/keycloak:26.8.2
COPY --from=builder /opt/keycloak/ /opt/keycloak/
COPY --chown=keycloak:keycloak --chmod=0750 infra/keycloak/render-entrypoint.sh /opt/keycloak/render-entrypoint.sh
USER keycloak
ENTRYPOINT ["/bin/bash", "/opt/keycloak/render-entrypoint.sh"]
