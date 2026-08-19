#!/usr/bin/env python3
"""Set railwayConfigFile on a named service in the linked Railway project."""

from __future__ import annotations

import json
import subprocess
import sys


def sh(*args: str) -> str:
    return subprocess.check_output(args, text=True)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} <service-name> <config-path>")
    name, path = sys.argv[1], sys.argv[2]
    status = json.loads(sh("railway", "status", "--json"))
    env_id = status["environments"]["edges"][0]["node"]["id"]
    try:
        svc_id = next(e["node"]["id"] for e in status["services"]["edges"] if e["node"]["name"] == name)
    except StopIteration:
        names = [e["node"]["name"] for e in status["services"]["edges"]]
        raise SystemExit(f"service {name!r} not found; have {names}") from None
    out = json.loads(
        sh(
            "railway",
            "api",
            "--variables",
            json.dumps(
                {
                    "serviceId": svc_id,
                    "environmentId": env_id,
                    "input": {"railwayConfigFile": path},
                }
            ),
            "mutation($serviceId: String!, $environmentId: String!, $input: ServiceInstanceUpdateInput!) { serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId, input: $input) }",
        )
    )
    if out.get("errors"):
        raise SystemExit(json.dumps(out, indent=2))
    print(f"{name} -> {path}")


if __name__ == "__main__":
    main()
