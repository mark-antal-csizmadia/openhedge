import { CopyButton } from "@/components/copy-button";

export function CodeBlock({
  code,
  filename,
}: {
  code: string;
  filename?: string;
}) {
  return (
    <div className="overflow-hidden rounded-lg ring-1 ring-foreground/10">
      {filename ? (
        <div className="flex items-center justify-between gap-3 border-b border-border/60 bg-muted/40 px-3 py-1.5">
          <span className="font-mono text-xs text-muted-foreground">{filename}</span>
          <CopyButton text={code} />
        </div>
      ) : null}
      <div className="relative">
        {!filename ? (
          <div className="absolute top-2 right-2">
            <CopyButton text={code} />
          </div>
        ) : null}
        <pre className="overflow-x-auto p-4 pr-24 text-[13px] leading-relaxed">
          <code className="font-mono text-foreground/90">{code}</code>
        </pre>
      </div>
    </div>
  );
}
