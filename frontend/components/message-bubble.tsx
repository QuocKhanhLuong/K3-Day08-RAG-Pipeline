import { Scale } from "lucide-react"
import type { Message } from "@/lib/mock-data"
import { CitationList } from "@/components/citation-card"
import { cn } from "@/lib/utils"

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user"

  return (
    <div className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Scale className="size-4" />
        </span>
      )}

      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-3 md:max-w-[75%]",
          isUser
            ? "rounded-br-sm bg-primary text-primary-foreground"
            : "rounded-bl-sm border border-border bg-card text-card-foreground",
        )}
      >
        <div className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</div>
        {message.citations && message.citations.length > 0 && (
          <CitationList citations={message.citations} />
        )}
      </div>
    </div>
  )
}

export function TypingBubble() {
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Scale className="size-4" />
      </span>
      <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-sm border border-border bg-card px-4 py-4">
        <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
        <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
        <span className="size-2 animate-bounce rounded-full bg-muted-foreground" />
      </div>
    </div>
  )
}
