#!/usr/bin/env python3
"""Fail unless the template asks only for OPENROUTER_API_KEY, pins PORT, and can Docker-build."""

from __future__ import annotations

import json
import subprocess
import sys


PORT_DEFAULTS = {"api": "8000", "mcp": "8001", "caddy": "8080"}
DOCKERFILE_PATHS = {
    "api": "openhedge-core/Dockerfile",
    "mcp": "openhedge-core/Dockerfile",
    "sync": "openhedge-core/Dockerfile",
    "caddy": "deploy/caddy/Dockerfile",
}
CONFIG_FILES = {
    "api": "/deploy/railway/api.toml",
    "mcp": "/deploy/railway/mcp.toml",
    "sync": "/deploy/railway/sync.toml",
    "caddy": "/deploy/railway/caddy.toml",
}
START_NEEDLES = {
    "api": ("openhedge_core.server", "API_PORT"),
    "mcp": ("openhedge_core.mcp_server", "MCP_PORT"),
    "sync": ("openhedge_core.sync_markets",),
}
HEALTHCHECK_SERVICES = ("api", "mcp", "caddy")
DROP_QDRANT = frozenset({"QDRANT__SERVICE__HTTP_PORT", "QDRANT__STORAGE__STORAGE_PATH"})


def sh(*args: str) -> str:
    return subprocess.check_output(args, text=True)


def redact(obj: object) -> object:
    if isinstance(obj, dict):
        out: dict[str, object] = {}
        for k, v in obj.items():
            lk = k.lower()
            if any(s in lk for s in ("key", "secret", "token", "password")) and isinstance(v, str) and v:
                out[k] = "<redacted>"
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    return obj


def norm_path(value: object) -> str:
    return str(value or "").strip().lstrip("/")


def dockerfile_path(svc: dict[str, object], name: str) -> str | None:
    expected = DOCKERFILE_PATHS[name]
    if svc.get("configFile") == CONFIG_FILES[name]:
        return expected
    build = svc.get("build") if isinstance(svc.get("build"), dict) else {}
    from_build = norm_path(build.get("dockerfilePath") if isinstance(build, dict) else None)
    if from_build == expected:
        return from_build
    variables = svc.get("variables") if isinstance(svc.get("variables"), dict) else {}
    spec = variables.get("RAILWAY_DOCKERFILE_PATH") if isinstance(variables, dict) else None
    spec = spec if isinstance(spec, dict) else {}
    from_var = norm_path(spec.get("defaultValue") or spec.get("value"))
    if from_var == expected:
        return from_var
    return None


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} <template-id-or-code>")
    ident = sys.argv[1]
    out = json.loads(
        sh(
            "railway",
            "api",
            "--variables",
            json.dumps({"id": ident}),
            "query($id: String!) { template(id: $id) { id code status serializedConfig } }",
        )
    )
    if out.get("errors") or not (out.get("data") or {}).get("template"):
        raise SystemExit(json.dumps(out, indent=2))
    tmpl = out["data"]["template"]
    cfg = tmpl["serializedConfig"]
    if isinstance(cfg, str):
        cfg = json.loads(cfg)
    services = (cfg or {}).get("services") or {}
    errors: list[str] = []
    required_empty: list[str] = []
    found_ports: dict[str, str | None] = {}
    found_docker: dict[str, str | None] = {}
    found_openrouter = False
    names: list[str] = []

    for sid, svc in services.items():
        name = svc.get("name") or sid
        names.append(name)
        variables = svc.get("variables") or {}
        net = ((svc.get("networking") or {}).get("serviceDomains")) or {}
        deploy = svc.get("deploy") if isinstance(svc.get("deploy"), dict) else {}
        source = svc.get("source") if isinstance(svc.get("source"), dict) else {}
        root_dir = (source or {}).get("rootDirectory")
        if name in DOCKERFILE_PATHS and root_dir:
            errors.append(
                f"{name}.source.rootDirectory must be empty, got {root_dir!r} "
                "(Dockerfiles COPY from the repo root; do not use Root Directory)"
            )
        if name in DOCKERFILE_PATHS:
            found_docker[name] = dockerfile_path(svc, name)
            if found_docker[name] != DOCKERFILE_PATHS[name]:
                errors.append(
                    f"{name} needs Dockerfile {DOCKERFILE_PATHS[name]!r} via optional "
                    f"RAILWAY_DOCKERFILE_PATH (composer has no Config File field; "
                    f"do not set Root Directory)"
                )
        elif name == "Qdrant" and svc.get("configFile"):
            errors.append(f"Qdrant: drop configFile {svc.get('configFile')!r} (image source; no toml)")
        if name in START_NEEDLES:
            start = str((deploy or {}).get("startCommand") or "")
            missing = [n for n in START_NEEDLES[name] if n not in start]
            if missing:
                errors.append(f"{name}.startCommand missing {missing}; paste from the Settings-tab kit")
        if name in HEALTHCHECK_SERVICES and (deploy or {}).get("healthcheckPath") != "/health":
            errors.append(f"{name}.healthcheckPath must be '/health' (Settings tab)")
        if name == "sync":
            if (deploy or {}).get("cronSchedule") != "0 * * * *":
                errors.append("sync.cronSchedule must be '0 * * * *' (Settings tab Cron Schedule)")
            restart = (deploy or {}).get("restartPolicyType")
            if restart and restart != "NEVER":
                errors.append(f"sync.restartPolicyType must be NEVER, got {restart!r}")
        if name in ("mcp", "Qdrant") and net:
            errors.append(f"{name}: public HTTP domain present; public HTTP only on caddy")
        if name == "caddy" and not net:
            errors.append("caddy: missing public HTTP service domain")
        if name in ("cloudflared", "Cloudflared"):
            errors.append("cloudflared must not be in the template")
        for key, spec in variables.items():
            spec = spec or {}
            default = spec.get("defaultValue")
            value = spec.get("value")
            optional = spec.get("isOptional")
            filled = bool(default) or bool(value)
            if name == "Qdrant" and key in DROP_QDRANT:
                errors.append(f"Qdrant: drop {key} (image default; do not prompt)")
            if name in PORT_DEFAULTS and key == "PORT":
                found_ports[name] = default or value
                if (default or value) != PORT_DEFAULTS[name]:
                    errors.append(f"{name}.PORT default must be {PORT_DEFAULTS[name]!r}, got {default or value!r}")
                if optional is False and not filled:
                    errors.append(f"{name}.PORT is required and empty; set default and mark optional")
            if name in DOCKERFILE_PATHS and key == "RAILWAY_DOCKERFILE_PATH":
                if (default or value) and norm_path(default or value) != DOCKERFILE_PATHS[name]:
                    errors.append(
                        f"{name}.RAILWAY_DOCKERFILE_PATH default must be {DOCKERFILE_PATHS[name]!r}, "
                        f"got {default or value!r}"
                    )
                if optional is False and not filled:
                    errors.append(f"{name}.RAILWAY_DOCKERFILE_PATH is required and empty; set default and mark optional")
            if key == "OPENROUTER_API_KEY":
                found_openrouter = True
                if filled:
                    errors.append(f"{name}.OPENROUTER_API_KEY must be empty (no default)")
                if optional is True:
                    errors.append(f"{name}.OPENROUTER_API_KEY must be required")
                desc = (spec.get("description") or "").strip()
                if not desc:
                    errors.append(f"{name}.OPENROUTER_API_KEY needs a description (marketplace required vars)")
            elif key in DROP_QDRANT:
                pass
            elif key in ("QDRANT_URL", "OPENHEDGE_API_URL", "UPSTREAM_URL", "RAILWAY_DOCKERFILE_PATH", "PORT"):
                if key in ("QDRANT_URL", "OPENHEDGE_API_URL", "UPSTREAM_URL") and optional is not True:
                    errors.append(f"{name}.{key} should be optional (keep default); else add a description")
            elif not filled and optional is not True:
                required_empty.append(f"{name}.{key}")

    for svc_name in PORT_DEFAULTS:
        if svc_name not in found_ports:
            errors.append(f"{svc_name}.PORT missing from template")
    for svc_name in DOCKERFILE_PATHS:
        if svc_name not in found_docker:
            errors.append(f"{svc_name} missing from template")
    extra = [x for x in required_empty if not x.endswith(".OPENROUTER_API_KEY")]
    if extra:
        errors.append("required empty vars besides OPENROUTER_API_KEY: " + ", ".join(extra))
    if not found_openrouter:
        errors.append("OPENROUTER_API_KEY is not a required empty var on api/sync")

    print(json.dumps({"id": tmpl["id"], "code": tmpl["code"], "status": tmpl["status"], "services": names}, indent=2))
    if errors:
        print(json.dumps({"errors": errors, "requiredEmpty": required_empty, "config": redact(cfg)}, indent=2))
        raise SystemExit(1)
    print("ok: only OPENROUTER_API_KEY is required; PORT defaults set; Dockerfiles and start commands set")


if __name__ == "__main__":
    main()
