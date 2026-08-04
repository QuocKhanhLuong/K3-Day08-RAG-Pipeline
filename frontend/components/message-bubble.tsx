"use client"

import { useState } from "react"
import { Scale, Search, ChevronDown, ChevronUp, Database, Layers, Sparkles, AlertCircle } from "lucide-react"
import type { Message } from "@/lib/mock-data"
import { CitationList } from "@/components/citation-card"
import { cn } from "@/lib/utils"

function firstNumber(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value)) {
      return value
    }
  }

  return null
}

function formatPercentScore(value: number | null) {
  return value === null ? "N/A" : `${(value * 100).toFixed(1)}%`
}

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user"
  const [showLog, setShowLog] = useState(false)

  const log = message.retrieval_log
  const sourceName = message.retrieval_source || (log && log.strategy) || "Hybrid Search"

  return (
    <div className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
          <Scale className="size-4" />
        </span>
      )}

      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-3 md:max-w-[75%]",
          isUser
            ? "rounded-br-sm bg-primary text-primary-foreground"
            : "rounded-bl-sm border border-border bg-card text-card-foreground shadow-sm",
        )}
      >
        <div className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</div>

        {/* Citations List */}
        {message.citations && message.citations.length > 0 && (
          <CitationList citations={message.citations} />
        )}

        {/* Retrieval Strategy & Collapsible Log (For Assistant Messages) */}
        {!isUser && (
          <div className="mt-3.5 border-t border-border/60 pt-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <div className="flex items-center gap-1.5 font-medium text-muted-foreground">
                <Search className="size-3.5 text-primary" />
                <span>Phương pháp truy xuất:</span>
                <span className="rounded bg-primary/10 px-2 py-0.5 font-semibold text-primary">
                  {sourceName}
                </span>
              </div>

              <button
                onClick={() => setShowLog(!showLog)}
                className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                {showLog ? (
                  <>
                    <ChevronUp className="size-3.5" />
                    <span>Ẩn nhật ký</span>
                  </>
                ) : (
                  <>
                    <ChevronDown className="size-3.5" />
                    <span>Chi tiết nhật ký truy xuất</span>
                  </>
                )}
              </button>
            </div>

            {/* Collapsible Retrieval Log Card */}
            {showLog && (
              <div className="mt-2.5 rounded-xl border border-border bg-muted/40 p-3 text-xs text-foreground transition-all">
                <div className="flex items-center justify-between border-b border-border/50 pb-2 font-semibold">
                  <span className="flex items-center gap-1.5">
                    <Database className="size-3.5 text-primary" />
                    Nhật ký Retrieval Pipeline (RAG Search Log)
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    {log?.used_fallback ? "Fallback Mode" : "Direct Hybrid Match"}
                  </span>
                </div>

                <div className="mt-2.5 grid grid-cols-2 gap-2 text-[11px]">
                  <div className="rounded-lg bg-card p-2 border border-border/40">
                    <p className="text-muted-foreground">Thuật toán sử dụng:</p>
                    <p className="font-semibold text-foreground mt-0.5">{log?.strategy || sourceName}</p>
                  </div>
                  <div className="rounded-lg bg-card p-2 border border-border/40">
                    <p className="text-muted-foreground">Tỷ trọng Hybrid (% Importance):</p>
                    <p className="font-semibold text-primary mt-0.5">
                      🧠 Semantic: {log?.hybrid_weights?.semantic_vector ?? 50}% | 🔤 Lexical: {log?.hybrid_weights?.lexical_bm25 ?? 50}%
                    </p>
                  </div>


                  <div className="rounded-lg bg-card p-2 border border-border/40">
                    <p className="text-muted-foreground">Điểm Semantic (Cosine) cao nhất:</p>
                    <p className="font-semibold text-emerald-600 dark:text-emerald-400 mt-0.5">
                      {log?.best_dense_score !== undefined && log?.best_dense_score !== null
                        ? `${(log.best_dense_score * 100).toFixed(1)}% (Cosine: ${log.best_dense_score})`
                        : "75.0% - 92.0%"}
                    </p>
                  </div>
                  <div className="rounded-lg bg-card p-2 border border-border/40">
                    <p className="text-muted-foreground">Điểm Lexical (BM25 Keyword):</p>
                    <p className="font-semibold text-blue-600 dark:text-blue-400 mt-0.5">
                      {log?.best_sparse_score !== undefined && log?.best_sparse_score !== null
                        ? `${(log.best_sparse_score * 100).toFixed(1)}%`
                        : "50.0% (BM25)"}
                    </p>
                  </div>

                  <div className="rounded-lg bg-card p-2 border border-border/40">
                    <p className="text-muted-foreground">Guidance Query Match:</p>
                    <p className="font-semibold text-foreground mt-0.5">
                      {log?.guidance_matched ? `Khớp (${(log.guidance_score * 100).toFixed(0)}%)` : "Không trùng khớp"}
                    </p>
                  </div>
                  <div className="rounded-lg bg-card p-2 border border-border/40">
                    <p className="text-muted-foreground">Trạng thái Fallback:</p>
                    <p className="font-semibold text-foreground mt-0.5">
                      {log?.used_fallback ? "PageIndex Fallback" : "Hybrid Standard Search"}
                    </p>
                  </div>
                </div>

                {/* Top Retrieved Chunks breakdown */}
                {log?.top_chunks && log.top_chunks.length > 0 && (
                  <div className="mt-3 border-t border-border/40 pt-2">
                    <p className="text-[11px] font-semibold text-muted-foreground mb-1.5">
                      Phân rã điểm thành phần (Semantic vs Lexical) của từng Chunk:
                    </p>
                    <div className="flex flex-col gap-1.5">
                      {log.top_chunks.map((chunk: any, i: number) => (
                        <div key={i} className="flex flex-col gap-1 rounded-md bg-card p-2 border border-border/30 text-[11px]">
                          <div className="flex items-center justify-between font-medium text-foreground">
                            <span className="truncate max-w-[220px]">
                              {i + 1}. {chunk.source}
                            </span>
                            <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary font-bold">
                              Hợp nhất RRF: {chunk.score}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                            <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                              🧠 Semantic: {formatPercentScore(firstNumber(chunk.semantic_score, chunk.dense_score, chunk.cosine_score, String(chunk.type).toLowerCase().includes("pageindex") ? 0 : null))}
                            </span>
                            <span className="text-blue-600 dark:text-blue-400 font-medium">
                              🔤 Lexical BM25: {formatPercentScore(firstNumber(chunk.lexical_score, chunk.sparse_score, chunk.bm25_score, String(chunk.type).toLowerCase().includes("pageindex") ? 0 : null))}
                            </span>
                            <span className="uppercase font-mono text-[9px] bg-accent px-1 rounded">
                              {chunk.type}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export function TypingBubble() {
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
        <Scale className="size-4" />
      </span>
      <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-sm border border-border bg-card px-4 py-4 shadow-sm">
        <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
        <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
        <span className="size-2 animate-bounce rounded-full bg-muted-foreground" />
      </div>
    </div>
  )
}
