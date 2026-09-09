import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CopyButton } from "@/components/copy-button";
import { ExampleOutput } from "@/components/example-output";
import { EXAMPLES } from "@/lib/examples";

export function ExamplePrompts() {
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        After the MCP is connected, paste one of these into your agent.
      </p>
      <p className="text-sm text-muted-foreground text-pretty">
        * Prefixing the examples with “Use the openhedge MCP server” can help in some cases,
        depending on your setup and the number of MCP servers you are already using.
      </p>
      <ul className="flex flex-col gap-3">
        {EXAMPLES.map((example) => (
          <li key={example.title}>
            <Card className="min-w-0">
              <CardHeader>
                <div className="flex flex-wrap items-center gap-2">
                  <CardTitle>{example.title}</CardTitle>
                  <Badge variant="outline">
                    {example.loc}, {example.chip}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="flex min-w-0 flex-col gap-3">
                <blockquote className="text-sm leading-relaxed text-foreground/90 text-pretty">
                  {example.prompt}
                </blockquote>
                <p className="text-sm leading-relaxed text-muted-foreground text-pretty">
                  {example.note}
                </p>
                <p className="text-sm text-muted-foreground">Updated {example.updatedAt}</p>
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <CopyButton text={example.prompt} label="Copy prompt" />
                  <ExampleOutput tools={example.output.tools} reply={example.output.reply} />
                </div>
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
