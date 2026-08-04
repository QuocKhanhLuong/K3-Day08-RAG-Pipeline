"use client"

import { useState } from "react"
import { Globe, ShieldCheck, AlertTriangle, CheckCircle2, Loader2, X, ExternalLink } from "lucide-react"

type CrawlModalProps = {
  open: boolean
  onClose: () => void
  onSuccess?: () => void
}

type CrawlResult = {
  status: "success" | "rejected" | "error"
  url?: string
  title?: string
  domain?: string
  issuing_authority?: string
  is_official?: boolean
  score?: number
  matched_keywords?: string[]
  word_count?: number
  is_update?: boolean
  message?: string
  reason?: string
}

export function CrawlModal({ open, onClose, onSuccess }: CrawlModalProps) {
  const [url, setUrl] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<CrawlResult | null>(null)

  if (!open) return null

  const handleCrawl = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.strip ? !url.trim() : !url) return

    setLoading(true)
    setResult(null)

    try {
      const res = await fetch("http://localhost:8000/api/crawl-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim() }),
      })

      const data = await res.json()
      setResult(data)
      if (data.status === "success" && onSuccess) {
        onSuccess()
      }
    } catch (err) {
      setResult({
        status: "error",
        reason: "Không thể kết nối đến server backend (http://localhost:8000). Vui lòng đảm bảo server đang chạy.",
      })
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setUrl("")
    setResult(null)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="relative w-full max-w-lg rounded-2xl border border-border bg-background p-6 shadow-2xl transition-all">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border pb-4">
          <div className="flex items-center gap-2.5">
            <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Globe className="size-5" />
            </span>
            <div>
              <h2 className="text-base font-semibold text-foreground">Nạp & Kiểm Duyệt Dữ Liệu URL</h2>
              <p className="text-xs text-muted-foreground">Crawl, đánh giá độ chính thống và lưu vào Vector Store</p>
            </div>
          </div>
          <button
            onClick={handleReset}
            className="rounded-lg p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Input Form */}
        <form onSubmit={handleCrawl} className="mt-4 flex flex-col gap-3">
          <label className="text-xs font-semibold text-foreground">Đường dẫn bài viết / văn bản (URL):</label>
          <div className="flex gap-2">
            <input
              type="url"
              required
              placeholder="https://baochinhphu.vn/..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={loading}
              className="flex-1 rounded-xl border border-input bg-card px-3.5 py-2.5 text-sm placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={loading || !url.trim()}
              className="flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Đang Crawl...
                </>
              ) : (
                "Kiểm duyệt"
              )}
            </button>
          </div>
        </form>

        {/* Results / Evaluation Report */}
        {result && (
          <div className="mt-5 flex flex-col gap-3">
            {result.status === "success" && (
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-emerald-900 dark:text-emerald-200">
                <div className="flex items-start gap-2.5">
                  <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-semibold">{result.message}</h3>
                    <p className="mt-1 line-clamp-2 text-xs font-medium">{result.title}</p>
                    
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                      <span className="flex items-center gap-1 rounded-full bg-emerald-600/20 px-2.5 py-1 text-emerald-700 dark:text-emerald-300 font-medium">
                        <ShieldCheck className="size-3.5" />
                        {result.is_official ? "Nguồn Chính Thống" : "Nguồn Đáng Tin Cậy"}
                      </span>
                      <span className="rounded-full bg-card px-2.5 py-1 text-muted-foreground border border-border">
                        Tên miền: {result.domain}
                      </span>
                      <span className="rounded-full bg-card px-2.5 py-1 text-muted-foreground border border-border">
                        Điểm tin cậy: {result.score}/100
                      </span>
                    </div>

                    {result.matched_keywords && result.matched_keywords.length > 0 && (
                      <div className="mt-2.5 flex flex-wrap gap-1">
                        <span className="text-[11px] text-muted-foreground mr-1">Từ khóa pháp luật:</span>
                        {result.matched_keywords.map((kw, i) => (
                          <span key={i} className="rounded bg-primary/10 px-1.5 py-0.5 text-[11px] text-primary">
                            {kw}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {result.status === "rejected" && (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-amber-900 dark:text-amber-200">
                <div className="flex items-start gap-2.5">
                  <AlertTriangle className="mt-0.5 size-5 shrink-0 text-amber-600 dark:text-amber-400" />
                  <div>
                    <h3 className="text-sm font-semibold">Từ chối cập nhật nguồn tin</h3>
                    <p className="mt-1 text-xs">{result.reason}</p>
                  </div>
                </div>
              </div>
            )}

            {result.status === "error" && (
              <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-destructive">
                <div className="flex items-start gap-2.5">
                  <AlertTriangle className="mt-0.5 size-5 shrink-0" />
                  <div>
                    <h3 className="text-sm font-semibold">Lỗi xử lý</h3>
                    <p className="mt-1 text-xs">{result.reason}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="mt-6 flex justify-end gap-2 border-t border-border pt-4">
          <button
            onClick={handleReset}
            className="rounded-xl border border-border bg-card px-4 py-2 text-xs font-medium text-foreground transition-colors hover:bg-accent"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  )
}
