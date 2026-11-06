#!/usr/bin/env bash
# Render Stage only. Never use start-dev or a bundled development database.
set -euo pipefail

require() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Required Keycloak Stage configuration is missing: ${name}" >&2
    exit 1
  fi
}

require DATABASE_URL
require KC_DB_USERNAME
require KC_DB_PASSWORD
require KC_BOOTSTRAP_ADMIN_USERNAME
require KC_BOOTSTRAP_ADMIN_PASSWORD
require RENDER_EXTERNAL_HOSTNAME

# Render's private connectionString is postgresql://user:password@host:port/db.
# Discard the credentials in its URI, and use separately injected DB fields.
# Never print the URL or credentials to logs.
case "$DATABASE_URL" in
  postgresql://*@*/*) ;;
  *)
    echo "Render PostgreSQL connection format is unsupported" >&2
    exit 1
    ;;
esac
db_endpoint="${DATABASE_URL##*@}"
case "$db_endpoint" in
  */*) ;;
  *)
    echo "Render PostgreSQL host/database is missing" >&2
    exit 1
    ;;
esac
if [[ "$db_endpoint" == *$'\n'* || "$db_endpoint" == *$'\r'* ]]; then
  echo "Render PostgreSQL endpoint is malformed" >&2
  exit 1
fi

export KC_DB_URL="jdbc:postgresql://${db_endpoint}"
unset DATABASE_URL
export KC_HOSTNAME="https://${RENDER_EXTERNAL_HOSTNAME}"
export KC_DB=postgres
export KC_HTTP_ENABLED=true
export KC_PROXY_HEADERS=xforwarded
export KC_HTTP_PORT="${PORT:-10000}"

# TLS must terminate at Render; Keycloak itself remains in production mode.
# Realm, OIDC client, national-ID claim, OTP and Shahkar integrations are NOT bootstrapped here.
exec /opt/keycloak/bin/kc.sh start --optimized
