#!/usr/bin/env python3
"""Create an empty Railway service via GraphQL (fallback when railway add fails)."""

from __future__ import annotations

import json
import subprocess
import sys


def sh(*args: str) -> str:
    return subprocess.check_output(args, text=True)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} <service-name>")
    name = sys.argv[1]
    status = json.loads(sh("railway", "status", "--json"))
    out = json.loads(
        sh(
            "railway",
            "api",
            "--variables",
            json.dumps(
                {
                    "input": {
                        "projectId": status["id"],
                        "name": name,
                        "environmentId": status["environments"]["edges"][0]["node"]["id"],
                    },
                }
            ),
            "mutation($input: ServiceCreateInput!) { serviceCreate(input: $input) { id name } }",
        )
    )
    print(json.dumps(out, indent=2))
    if out.get("errors") or not (out.get("data") or {}).get("serviceCreate"):
        raise SystemExit("serviceCreate failed")


if __name__ == "__main__":
    main()
