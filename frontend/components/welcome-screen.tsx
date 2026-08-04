import { Scale, ArrowUpRight } from "lucide-react"
import { suggestedQuestions } from "@/lib/mock-data"

export function WelcomeScreen({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col items-center px-4 py-10 text-center md:py-16">
      <span className="flex size-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
        <Scale className="size-7" />
      </span>
      <h1 className="mt-5 text-balance font-serif text-2xl font-semibold text-foreground md:text-3xl">
        Hiểu quyền lao động của bạn, đơn giản và rõ ràng
      </h1>
      <p className="mt-3 max-w-md text-pretty text-sm leading-relaxed text-muted-foreground">
        Hỏi bất cứ điều gì về thử việc, làm thêm giờ, nghỉ phép, hợp đồng hay sa thải. Câu trả lời luôn kèm căn cứ từ
        Bộ luật Lao động 2019.
      </p>

      <div className="mt-8 w-full">
        <p className="mb-3 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Câu hỏi gợi ý
        </p>
        <div className="grid gap-2.5 sm:grid-cols-2">
          {suggestedQuestions.map((q, i) => (
            <button
              key={i}
              onClick={() => onPick(q)}
              className="group flex items-start gap-2 rounded-xl border border-border bg-card p-3.5 text-left text-sm leading-snug text-foreground/90 transition-colors hover:border-primary hover:bg-accent/50"
            >
              <span className="flex-1">{q}</span>
              <ArrowUpRight className="mt-0.5 size-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
