#!/usr/bin/env python3
"""Fail-closed audit of fully resolved Docker Compose JSON for Wacom staging.

Reads stdin only; never prints the Compose JSON (which can contain secrets).
Must be run on docker compose config --format json, not hand-written YAML.
Does not deploy, pull images, connect to databases, or create resources.
"""
from __future__ import annotations

import json
import sys


def audit(config: dict) -> list[str]:
    blockers: list[str] = []
    services = config.get("services", {})
    project = config.get("name", "")
    if not project.startswith("loanhub-wacom-stage"):
        blockers.append("unexpected_compose_project")
    if not isinstance(services, dict) or not all(name in services for name in ("backend", "db", "redis", "migrate", "clamav")):
        return blockers + ["required_services_missing"]

    def env(name):
        values = services[name].get("environment") or {}
        if isinstance(values, list):
            values = dict(item.split("=", 1) for item in values if "=" in item)
        return values

    backend = services["backend"]
    db = services["db"]
    scan = services["clamav"]
    migrate = services["migrate"]
    benv = env("backend")
    denv = env("db")

    if denv.get("POSTGRES_DB", "") not in {"loanhub_wacom_staging", "loanhub_wacom_test"}:
        blockers.append("database_name_not_dedicated")
    for key in ("FILE_ENCRYPTION_ENABLED", "MALWARE_SCAN_ENABLED", "MALWARE_SCAN_FAIL_CLOSED"):
        if str(benv.get(key, "")).lower() != "true":
            blockers.append(key.lower() + "_not_enabled")
    if benv.get("CLAMAV_HOST") != "clamav" or str(benv.get("CLAMAV_PORT")) != "3310":
        blockers.append("backend_scanner_endpoint_not_private")
    if "/staging/" not in str(benv.get("FILE_STORAGE_PATH", "")):
        blockers.append("storage_path_not_staging")
    if benv.get("ENVIRONMENT") != "staging":
        blockers.append("backend_not_staging")
    if str(benv.get("LELEFAPAYGATE_ENABLED", "")).lower() != "false":
        blockers.append("payment_gate_not_disabled")

    # Compose service ports are objects with published/target/host_ip keys.
    def published(service):
        return service.get("ports") or []

    for name, service in services.items():
        networks = service.get("networks") or {}
        if isinstance(networks, list):
            keys = networks
        else:
            keys = networks.keys()
        if any("public" in name.lower() or "edge" in name.lower() for name in keys):
            blockers.append("public_network_service_" + name)
        if name not in {"backend", "frontend"} and published(service):
            blockers.append("unexpected_published_port_" + name)
        for port in published(service):
            host = str(port.get("host_ip", ""))
            if host != "127.0.0.1":
                blockers.append("non_loopback_port_" + name)

    if published(scan):
        blockers.append("clamav_must_have_no_published_ports")
    backend_ports = published(backend)
    if len(backend_ports) != 1 or str(backend_ports[0].get("target")) != "8000":
        blockers.append("unexpected_backend_binding")
    elif not (18000 <= int(backend_ports[0].get("published", 0)) <= 18999):
        blockers.append("backend_staging_port_outside_reserved_range")

    for name, service in (("backend", backend), ("migrate", migrate)):
        volumes = service.get("volumes") or []
        if not any(
            "staging-secrets" in str(item.get("source", ""))
            and str(item.get("target", "")) == "/app/secrets"
            and bool(item.get("read_only"))
            for item in volumes
        ):
            blockers.append(name + "_staging_secrets_not_readonly")

    volumes = config.get("volumes") or {}
    if not isinstance(volumes, dict):
        blockers.append("unrecognized_volume_definition")
    else:
        for name in ("postgres_data", "redis_data", "loanhub_files"):
            v = volumes.get(name)
            if not isinstance(v, dict) or not str(v.get("name", "")).startswith(project + "_"):
                blockers.append("unscoped_" + name + "_volume")
            elif v.get("external", False):
                blockers.append("external_" + name + "_volume")

    # No project-shared external networks. Do not use production public-edge.
    for name, network in (config.get("networks") or {}).items():
        if isinstance(network, dict) and network.get("external", False):
            blockers.append("external_network_" + name)
    return sorted(set(blockers))


def main():
    try:
        resolved = json.load(sys.stdin)
        problems = audit(resolved)
    except (ValueError, TypeError, KeyError):
        problems = ["invalid_compose_configuration"]
    if problems:
        print("WACOM RESOLVED COMPOSE: BLOCKED")
        for problem in problems:
            print("BLOCKER:", problem)
        return 1
    print("WACOM RESOLVED COMPOSE: STRUCTURAL ISOLATION CHECK PASSED")
    print("Not a deployment authorization or proof of physical/runtime isolation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
