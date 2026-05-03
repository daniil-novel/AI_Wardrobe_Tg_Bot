from pathlib import Path


def test_compose_can_start_without_required_env_file() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "env_file: .env" not in compose
    assert "${OPENROUTER_API_KEY:-}" in compose
    assert "${API_HOST_PORT:-8000}:8000" in compose
    assert "http://localhost:8000/health" in compose
    assert "profiles:\n      - telegram" in compose


def test_dockerignore_keeps_secrets_and_node_modules_out_of_build_context() -> None:
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8")

    assert ".env" in dockerignore
    assert "apps/miniapp/node_modules" in dockerignore
    assert ".git" in dockerignore


def test_env_example_exposes_port_overrides_without_secrets() -> None:
    env_example = Path(".env.example").read_text(encoding="utf-8")

    for key in ("API_HOST_PORT", "MINIAPP_HOST_PORT", "POSTGRES_HOST_PORT"):
        assert key in env_example
    assert "OPENROUTER_API_KEY=" in env_example
