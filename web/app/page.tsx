import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { CopyButton } from "@/components/copy-button";
import { ExamplePrompts } from "@/components/example-prompts";
import { InstallTabs } from "@/components/install-tabs";
import { Mark } from "@/components/mark";
import { BLANKET_URL, GITHUB_URL, MCP_URL, SELF_HOST_URL, X_HANDLE, X_URL } from "@/lib/mcp";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="mx-auto flex w-full max-w-3xl items-center px-6 py-6">
        <div className="flex items-center gap-2.5">
          <Mark className="size-8" />
          <span className="text-sm font-medium tracking-tight">openhedge</span>
        </div>
        <nav className="ml-6 flex items-center gap-4">
          <a
            href={GITHUB_URL}
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            GitHub
          </a>
          <a
            href={X_URL}
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            {X_HANDLE}
          </a>
        </nav>
      </header>

      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-14 px-6 pb-20 pt-8 sm:pt-16">
        <section className="flex flex-col gap-6">
          <Badge variant="outline">MCP</Badge>
          <h1 className="max-w-2xl font-heading text-3xl leading-[1.15] tracking-tight text-balance sm:text-4xl">
            Open source experimental tool for discovering relevant hedges using event
            contracts and prediction markets
          </h1>
          <p className="max-w-lg text-base leading-relaxed text-muted-foreground text-pretty">
            Inspired by{" "}
            <a href={BLANKET_URL} className="text-foreground underline-offset-4 hover:underline">
              Blanket
            </a>
            . It does not hold money or place trades. Install the hosted MCP in Grok, Cursor,
            Codex, or Claude.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="flex min-w-0 flex-1 items-center justify-between gap-3 rounded-lg bg-card px-3 py-2 ring-1 ring-foreground/10">
              <code className="truncate font-mono text-sm text-foreground/90">{MCP_URL}</code>
              <CopyButton text={MCP_URL} />
            </div>
          </div>
          <p className="text-xs tracking-wide text-muted-foreground uppercase">
            Unauthenticated · rate limited · experimental
          </p>
        </section>

        <Separator />

        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium tracking-tight">Install</h2>
          <InstallTabs />
        </section>

        <Separator />

        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium tracking-tight">Examples</h2>
          <ExamplePrompts />
        </section>
      </main>

      <footer className="mx-auto flex w-full max-w-3xl flex-col gap-3 px-6 py-8 text-sm text-muted-foreground">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <span>Does not place trades.</span>
          <a href={GITHUB_URL} className="hover:text-foreground">
            GitHub
          </a>
          <a href={SELF_HOST_URL} className="hover:text-foreground">
            Self-host
          </a>
        </div>
        <p>
          Independently developed by{" "}
          <a href={X_URL} className="text-foreground underline-offset-4 hover:underline">
            {X_HANDLE}
          </a>
        </p>
      </footer>
    </div>
  );
}
