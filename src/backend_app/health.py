"""Local backend health checks for optional service integrations."""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Sequence

from planning import LangGraphCompatibleOrchestrationAdapter, LocalPlannedQueryGraphApp, OrchestrationStatus
from storage import BackendStatus, Neo4jGraphBackendAdapter, QdrantVectorBackendAdapter


OPTIONAL_IMPORTS = (
    ("qdrant-client", "qdrant_client"),
    ("neo4j", "neo4j"),
    ("langgraph", "langgraph"),
    ("llama-index-core", "llama_index.core"),
)


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    status: str
    detail: str


def run_health_checks(
    *,
    strict_services: bool = False,
    env_file: str | None = ".env",
) -> tuple[CheckResult, ...]:
    if env_file:
        _load_env_file(env_file)
    checks: list[CheckResult] = []
    checks.extend(_optional_import_checks())
    docker = _docker_check()
    checks.append(docker)
    checks.extend(_service_env_checks())
    checks.append(_qdrant_check(strict_services=strict_services, docker_available=docker.ok))
    checks.append(_neo4j_check(strict_services=strict_services, docker_available=docker.ok))
    checks.append(_langgraph_check())
    return tuple(checks)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check local backend environment health.")
    parser.add_argument(
        "--strict-services",
        action="store_true",
        help="Return a failure exit code when Qdrant or Neo4j services are unavailable.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Environment file to load before checks. Use an empty value to skip file loading.",
    )
    args = parser.parse_args(argv)

    checks = run_health_checks(strict_services=args.strict_services, env_file=args.env_file or None)
    for check in checks:
        marker = "OK" if check.ok else "WARN"
        print(f"[{marker}] {check.name}: {check.status} - {check.detail}")
    if args.strict_services:
        return 0 if all(check.ok for check in checks) else 1
    required_names = {package_name for package_name, _module_name in OPTIONAL_IMPORTS}
    required_names.add("langgraph-runtime")
    required_checks = [check for check in checks if check.name in required_names]
    return 0 if all(check.ok for check in required_checks) else 1


def _optional_import_checks() -> tuple[CheckResult, ...]:
    checks = []
    for package_name, module_name in OPTIONAL_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            checks.append(CheckResult(package_name, False, "missing", type(exc).__name__))
        else:
            checks.append(CheckResult(package_name, True, "installed", module_name))
    return tuple(checks)


def _load_env_file(path: str) -> None:
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _docker_check() -> CheckResult:
    docker = shutil.which("docker")
    if docker is None:
        return CheckResult("docker", False, "missing", "Docker CLI is not on PATH; compose services cannot be started here.")
    try:
        result = subprocess.run(
            [docker, "compose", "version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        return CheckResult("docker", False, "error", f"{type(exc).__name__}: {exc}")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or "docker compose version failed"
        return CheckResult("docker", False, "compose_unavailable", detail)
    return CheckResult("docker", True, "available", result.stdout.strip())


def _service_env_checks() -> tuple[CheckResult, ...]:
    required = {
        "QDRANT_URL": os.getenv("QDRANT_URL"),
        "NEO4J_URI": os.getenv("NEO4J_URI"),
        "NEO4J_USER": os.getenv("NEO4J_USER"),
        "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD"),
    }
    checks = []
    for key, value in required.items():
        if value:
            checks.append(CheckResult(key, True, "set", _redact(key, value)))
        else:
            checks.append(CheckResult(key, False, "unset", f"Set {key} or copy .env.example to .env before service checks."))
    defaulted = {
        "QDRANT_COLLECTION": (os.getenv("QDRANT_COLLECTION"), "evidence_chunks"),
        "NEO4J_DATABASE": (os.getenv("NEO4J_DATABASE"), "neo4j"),
    }
    for key, (value, default) in defaulted.items():
        if value:
            checks.append(CheckResult(key, True, "set", value))
        else:
            checks.append(CheckResult(key, True, "default", default))
    return tuple(checks)


def _qdrant_check(*, strict_services: bool, docker_available: bool) -> CheckResult:
    if not strict_services:
        return CheckResult("qdrant-service", True, "not_checked", "Use --strict-services to connect to Qdrant.")
    if not docker_available and _is_local_url(os.getenv("QDRANT_URL")):
        return CheckResult("qdrant-service", False, "blocked", "Docker is unavailable for local Qdrant service startup.")
    health = QdrantVectorBackendAdapter().health_check(correlation_id="corr_qdrant_health_cli")
    ok = health.status is not BackendStatus.UNAVAILABLE
    return CheckResult("qdrant-service", ok, health.status.value, health.message)


def _neo4j_check(*, strict_services: bool, docker_available: bool) -> CheckResult:
    if not strict_services:
        return CheckResult("neo4j-service", True, "not_checked", "Use --strict-services to connect to Neo4j.")
    if not docker_available and _is_local_url(os.getenv("NEO4J_URI")):
        return CheckResult("neo4j-service", False, "blocked", "Docker is unavailable for local Neo4j service startup.")
    health = Neo4jGraphBackendAdapter().health_check(correlation_id="corr_neo4j_health_cli")
    ok = health.status is not BackendStatus.UNAVAILABLE
    return CheckResult("neo4j-service", ok, health.status.value, health.message)


def _langgraph_check() -> CheckResult:
    health = LangGraphCompatibleOrchestrationAdapter(
        graph_app=LocalPlannedQueryGraphApp()
    ).health_check(correlation_id="corr_langgraph_health_cli")
    ok = health.status in {OrchestrationStatus.READY, OrchestrationStatus.DEGRADED}
    return CheckResult("langgraph-runtime", ok, health.status.value, health.message)


def _redact(key: str, value: str) -> str:
    if "PASSWORD" in key or "KEY" in key:
        return "<set>"
    return value


def _is_local_url(value: str | None) -> bool:
    if not value:
        return True
    normalized = value.lower()
    return "localhost" in normalized or "127.0.0.1" in normalized or "[::1]" in normalized


if __name__ == "__main__":
    raise SystemExit(main())
