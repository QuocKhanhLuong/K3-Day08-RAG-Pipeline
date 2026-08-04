"use client"

import { useRef, useState, type KeyboardEvent } from "react"
import { ArrowUp } from "lucide-react"
import { cn } from "@/lib/utils"

export function ChatInput({ onSend, disabled }: { onSend: (text: string) => void; disabled?: boolean }) {
  const [value, setValue] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue("")
    if (textareaRef.current) textareaRef.current.style.height = "auto"
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      if (e.nativeEvent.isComposing || e.keyCode === 229) return
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="border-t border-border bg-background/80 px-4 py-3 backdrop-blur md:px-6 md:py-4">
      <div className="mx-auto flex w-full max-w-3xl items-end gap-2 rounded-2xl border border-border bg-card p-2 shadow-sm focus-within:border-primary">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            e.target.style.height = "auto"
            e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`
          }}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Nhập câu hỏi về luật lao động của bạn..."
          className="max-h-40 flex-1 resize-none bg-transparent px-2 py-2 text-sm leading-relaxed text-foreground outline-none placeholder:text-muted-foreground"
        />
        <button
          onClick={submit}
          disabled={disabled || !value.trim()}
          aria-label="Gửi câu hỏi"
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-xl transition-colors",
            value.trim() && !disabled
              ? "bg-primary text-primary-foreground hover:opacity-90"
              : "cursor-not-allowed bg-muted text-muted-foreground",
          )}
        >
          <ArrowUp className="size-4" />
        </button>
      </div>
      <p className="mx-auto mt-2 max-w-3xl text-center text-[11px] text-muted-foreground">
        Nhấn Enter để gửi, Shift + Enter để xuống dòng.
      </p>
    </div>
  )
}
