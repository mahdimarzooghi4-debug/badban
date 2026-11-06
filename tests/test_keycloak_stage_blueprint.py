"""Static safeguards for the opt-in, unapproved Keycloak Stage Blueprint."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "render-keycloak-stage.yaml"
DOCKERFILE = ROOT / "infra" / "keycloak" / "Dockerfile"
ENTRYPOINT = ROOT / "infra" / "keycloak" / "render-entrypoint.sh"


def test_stage_blueprint_requires_separate_approval_and_paid_plan() -> None:
    config = BLUEPRINT.read_text(encoding="utf-8")
    assert "badban-keycloak-stage-db" in config
    assert "badban-keycloak-stage" in config
    assert "plan: standard" in config
    assert "autoDeployTrigger: off" in config
    assert "dockerfilePath: ./infra/keycloak/Dockerfile" in config
    assert "ipAllowList: []" in config
    assert "property: connectionString" in config
    assert "property: password" in config
    assert "property: user" in config
    assert "generateValue: true" in config
    assert "KC_BOOTSTRAP_ADMIN_PASSWORD\n        value:" not in config
    assert "KC_DB_PASSWORD\n        value:" not in config
    assert "badban-stage-db" not in config  # No sharing the financial DB.
    assert "secret" not in config.lower() or "credentials" not in config.lower()


def test_stage_container_uses_pinned_production_keycloak() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    entrypoint = ENTRYPOINT.read_text(encoding="utf-8")
    assert dockerfile.count("quay.io/keycloak/keycloak:26.8.2") == 2
    assert "latest" not in dockerfile
    assert "start-dev" not in dockerfile
    assert "exec /opt/keycloak/bin/kc.sh start --optimized" in entrypoint
    assert "KC_HTTP_ENABLED=true" in entrypoint
    assert "KC_PROXY_HEADERS=xforwarded" in entrypoint
    assert 'unset DATABASE_URL' in entrypoint
    assert "RENDER_EXTERNAL_HOSTNAME" in entrypoint
    assert "BADBAN_OIDC_ISSUER" not in entrypoint
    assert "SMS" not in entrypoint and "SHAHKAR" not in entrypoint


def test_stage_script_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(ENTRYPOINT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_stage_script_fails_closed_without_database_details() -> None:
    result = subprocess.run(
        ["bash", str(ENTRYPOINT)],
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "DATABASE_URL" in result.stderr
