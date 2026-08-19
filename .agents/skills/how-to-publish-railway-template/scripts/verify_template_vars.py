#!/usr/bin/env python3
"""Fail unless the template asks only for OPENROUTER_API_KEY and pins PORT defaults."""

from __future__ import annotations

import json
import subprocess
import sys


PORT_DEFAULTS = {"api": "8000", "mcp": "8001", "caddy": "8080"}
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
    names: list[str] = []

    for sid, svc in services.items():
        name = svc.get("name") or sid
        names.append(name)
        variables = svc.get("variables") or {}
        net = ((svc.get("networking") or {}).get("serviceDomains")) or {}
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
            if key == "OPENROUTER_API_KEY":
                if filled:
                    errors.append(f"{name}.OPENROUTER_API_KEY must be empty (no default)")
                if optional is True:
                    errors.append(f"{name}.OPENROUTER_API_KEY must be required")
                desc = (spec.get("description") or "").strip()
                if not desc:
                    errors.append(f"{name}.OPENROUTER_API_KEY needs a description (marketplace required vars)")
            elif key in DROP_QDRANT:
                pass
            elif key in ("QDRANT_URL", "OPENHEDGE_API_URL", "UPSTREAM_URL"):
                if optional is not True:
                    errors.append(f"{name}.{key} should be optional (keep default); else add a description")
            elif not filled and optional is not True:
                required_empty.append(f"{name}.{key}")

    for svc_name in PORT_DEFAULTS:
        if svc_name not in found_ports:
            errors.append(f"{svc_name}.PORT missing from template")
    extra = [x for x in required_empty if not x.endswith(".OPENROUTER_API_KEY")]
    keys_only = [x.split(".", 1)[1] for x in required_empty]
    if extra:
        errors.append("required empty vars besides OPENROUTER_API_KEY: " + ", ".join(extra))
    if "OPENROUTER_API_KEY" not in keys_only:
        errors.append("OPENROUTER_API_KEY is not a required empty var on api/sync")

    print(json.dumps({"id": tmpl["id"], "code": tmpl["code"], "status": tmpl["status"], "services": names}, indent=2))
    if errors:
        print(json.dumps({"errors": errors, "requiredEmpty": required_empty, "config": redact(cfg)}, indent=2))
        raise SystemExit(1)
    print("ok: only OPENROUTER_API_KEY is required; PORT defaults set")


if __name__ == "__main__":
    main()
