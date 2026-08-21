#!/usr/bin/env python3
"""Refuse if the linked Railway project looks like the OSS stack."""

from __future__ import annotations

import json
import subprocess

OSS = frozenset({"Qdrant", "api", "sync", "mcp", "caddy"})


def main() -> None:
    status = json.loads(subprocess.check_output(["railway", "status", "--json"], text=True))
    names = [edge["node"]["name"] for edge in status["services"]["edges"]]
    hit = sorted(OSS.intersection(names))
    if hit:
        raise SystemExit(f"refusing: this project has OSS services {hit}. Link a new empty project.")
    print("ok: not the OSS stack")


if __name__ == "__main__":
    main()
