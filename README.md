# openhedge

Open source experimental tool for discovering relevant hedges using event contracts and prediction markets.

## Components

- **openhedge-core** — Python 3.12+ library (`openhedge-core/src/openhedge_core`)

## Development

Requires [uv](https://docs.astral.sh/uv/) and [pre-commit](https://pre-commit.com/).

```bash
# uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# pre-commit
uv tool install pre-commit
```

From the repo root:

```bash
uv sync --project openhedge-core
pre-commit install
```

Run all hooks:

```bash
pre-commit run --all-files
```

## Docker

```bash
docker compose up
```

- REST API: `http://localhost:8000`
- MCP (Streamable HTTP): `http://localhost:8001/mcp`

Example MCP client config:

```json
{
  "mcpServers": {
    "openhedge": {
      "url": "http://localhost:8001/mcp"
    }
  }
}
```
