"use client";

import { useId, useState } from "react";

import { Button } from "@/components/ui/button";

export function ExampleOutput({
  tools,
  reply,
}: {
  tools: readonly { name: string; args: string }[];
  reply: string;
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((next) => !next)}
      >
        {open ? "Hide example output" : "View example output"}
      </Button>
      {open ? (
        <div id={panelId} className="flex w-full min-w-0 basis-full flex-col gap-3">
          <ol className="flex min-w-0 flex-col gap-1.5 font-mono text-[13px] leading-relaxed text-foreground/90">
            {tools.map((tool, index) => (
              <li key={`${tool.name}-${index}`} className="min-w-0 wrap-break-word">
                <span className="text-muted-foreground">{index + 1}. </span>
                <span>{tool.name}</span>{" "}
                <span className="text-muted-foreground">{tool.args}</span>
              </li>
            ))}
          </ol>
          <div className="min-w-0 overflow-hidden rounded-lg ring-1 ring-foreground/10">
            <pre className="max-h-[28rem] min-w-0 overflow-auto p-4 text-[13px] leading-relaxed whitespace-pre-wrap wrap-break-word">
              <code className="font-mono text-foreground/90">{reply}</code>
            </pre>
          </div>
        </div>
      ) : null}
    </>
  );
}
