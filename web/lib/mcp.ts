export const MCP_URL = "https://mcp.openhedge.app/mcp";
export const SITE_URL = "https://openhedge.app";
export const GITHUB_URL = "https://github.com/mark-antal-csizmadia/openhedge";
export const X_URL = "https://x.com/markcsizmadia";
export const X_HANDLE = "@markcsizmadia";
export const BLANKET_URL = "https://tryblanket.app/";
export const SELF_HOST_URL = `${GITHUB_URL}#deploy-on-railway`;

export const CURSOR_INSTALL_URL =
  "cursor://anysphere.cursor-deeplink/mcp/install?name=openhedge&config=eyJ1cmwiOiJodHRwczovL21jcC5vcGVuaGVkZ2UuYXBwL21jcCJ9";

export const grokCli = `grok mcp add --transport http openhedge ${MCP_URL}`;

export const grokToml = `[mcp_servers.openhedge]
url = "${MCP_URL}"`;

export const cursorJson = `{
  "mcpServers": {
    "openhedge": {
      "url": "${MCP_URL}"
    }
  }
}`;

export const codexCli = `codex mcp add openhedge --url ${MCP_URL}`;

export const codexToml = `[mcp_servers.openhedge]
url = "${MCP_URL}"`;
