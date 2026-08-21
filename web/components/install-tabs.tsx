"use client";

import { useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CodeBlock } from "@/components/code-block";
import {
  CURSOR_INSTALL_URL,
  MCP_URL,
  codexCli,
  codexToml,
  cursorJson,
  grokCli,
  grokToml,
} from "@/lib/mcp";
import { cn } from "@/lib/utils";

export function InstallTabs() {
  const [tab, setTab] = useState("grok");

  return (
    <Tabs value={tab} onValueChange={(next) => setTab(String(next))}>
      <TabsList className="grid h-auto w-full grid-cols-2 sm:grid-cols-4">
        <TabsTrigger value="grok">Grok</TabsTrigger>
        <TabsTrigger value="cursor">Cursor</TabsTrigger>
        <TabsTrigger value="codex">Codex</TabsTrigger>
        <TabsTrigger value="claude">Claude</TabsTrigger>
      </TabsList>

      <TabsContent value="grok" keepMounted>
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>Grok</CardTitle>
            <CardDescription>
              Grok Build CLI. No auth header — the hosted MCP is unauthenticated.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <CodeBlock filename="terminal" code={grokCli} />
            <CodeBlock filename="~/.grok/config.toml" code={grokToml} />
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="cursor" keepMounted>
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>Cursor</CardTitle>
            <CardDescription>
              One-click install, or paste into Settings → Tools & MCP. Do not add a{" "}
              <code className="font-mono text-foreground">type</code> field.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <a href={CURSOR_INSTALL_URL} className={cn(buttonVariants(), "w-fit")}>
              Add to Cursor
            </a>
            <CodeBlock filename=".cursor/mcp.json" code={cursorJson} />
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="codex" keepMounted>
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>Codex</CardTitle>
            <CardDescription>
              Codex CLI, ChatGPT desktop, and the IDE extension share{" "}
              <code className="font-mono text-foreground">~/.codex/config.toml</code>.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <CodeBlock filename="terminal" code={codexCli} />
            <CodeBlock filename="~/.codex/config.toml" code={codexToml} />
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="claude" keepMounted>
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>Claude</CardTitle>
            <CardDescription>
              Remote custom connector — not{" "}
              <code className="font-mono text-foreground">claude_desktop_config.json</code>.
              Skip OAuth fields. Free plans allow one custom connector.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 text-sm leading-relaxed text-muted-foreground">
            <ol className="list-decimal space-y-2 pl-5 text-foreground/90">
              <li>
                Open <span className="text-foreground">Customize → Connectors</span>
              </li>
              <li>Add a custom connector and paste the MCP URL</li>
              <li>Leave OAuth Client ID and Secret empty</li>
            </ol>
            <CodeBlock filename="MCP URL" code={MCP_URL} />
            <p>
              Claude reaches this URL from Anthropic’s cloud. The hosted MCP is already public.
            </p>
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  );
}
