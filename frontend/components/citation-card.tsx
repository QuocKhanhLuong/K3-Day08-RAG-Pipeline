import { BookOpen } from "lucide-react"
import type { Citation } from "@/lib/mock-data"

export function CitationList({ citations }: { citations: Citation[] }) {
  return (
    <div className="mt-4 flex flex-col gap-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Căn cứ pháp lý</p>
      {citations.map((c, i) => (
        <div key={i} className="rounded-lg border border-border bg-accent/50 p-3">
          <div className="flex items-center gap-2">
            <BookOpen className="size-3.5 shrink-0 text-primary" />
            <span className="text-xs font-semibold text-primary">{c.article}</span>
          </div>
          <p className="mt-1.5 text-sm leading-relaxed text-foreground/80">{c.excerpt}</p>
          <p className="mt-1.5 text-xs text-muted-foreground">— {c.source}</p>
        </div>
      ))}
    </div>
  )
}
