"use client"

import { Scale, Plus, MessageSquare, X, Trash2, Globe } from "lucide-react"
import { topics, type Conversation } from "@/lib/mock-data"

import { cn } from "@/lib/utils"

type AppSidebarProps = {
  open: boolean
  onClose: () => void
  conversations: Conversation[]
  activeConversation: string | null
  onSelectConversation: (id: string) => void
  onDeleteConversation?: (id: string) => void
  onSelectTopic: (label: string) => void
  onNewChat: () => void
  onOpenCrawlModal?: () => void
}

export function AppSidebar({
  open,
  onClose,
  conversations,
  activeConversation,
  onSelectConversation,
  onDeleteConversation,
  onSelectTopic,
  onNewChat,
  onOpenCrawlModal,
}: AppSidebarProps) {
  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <button
          aria-label="Đóng thanh bên"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-foreground/40 md:hidden"
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-transform duration-300 md:static md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {/* Brand */}
        <div className="flex items-center justify-between gap-2 border-b border-sidebar-border px-5 py-4">
          <div className="flex items-center gap-2.5">
            <span className="flex size-9 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
              <Scale className="size-5" />
            </span>
            <div className="leading-tight">
              <p className="font-serif text-base font-semibold">Luật Cùng Bạn</p>
              <p className="text-xs text-muted-foreground">Trợ lý Luật Lao Động</p>
            </div>
          </div>
          <button
            aria-label="Đóng thanh bên"
            onClick={onClose}
            className="text-muted-foreground md:hidden"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-2 px-4 pt-4">
          <button
            onClick={onNewChat}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-sidebar-primary px-4 py-2.5 text-sm font-medium text-sidebar-primary-foreground transition-opacity hover:opacity-90"
          >
            <Plus className="size-4" />
            Cuộc trò chuyện mới
          </button>

          {onOpenCrawlModal && (
            <button
              onClick={onOpenCrawlModal}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-sidebar-border bg-card px-4 py-2 text-xs font-medium text-sidebar-foreground transition-colors hover:border-sidebar-primary hover:text-sidebar-primary"
            >
              <Globe className="size-3.5" />
              Nạp & Crawl dữ liệu từ URL
            </button>
          )}
        </div>


        <div className="flex-1 overflow-y-auto px-4 py-5">
          {/* Quick topics */}
          <section>
            <h2 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Chủ đề nhanh
            </h2>
            <div className="flex flex-wrap gap-1.5">
              {topics.map((topic) => {
                const Icon = topic.icon
                return (
                  <button
                    key={topic.id}
                    onClick={() => onSelectTopic(topic.label)}
                    className="flex items-center gap-1.5 rounded-full border border-sidebar-border bg-card px-3 py-1.5 text-xs font-medium text-sidebar-foreground transition-colors hover:border-sidebar-primary hover:text-sidebar-primary"
                  >
                    <Icon className="size-3.5" />
                    {topic.label}
                  </button>
                )
              })}
            </div>
          </section>

          {/* History */}
          <section className="mt-7">
            <h2 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Lịch sử hội thoại
            </h2>
            {conversations.length === 0 ? (
              <p className="px-1 text-xs text-muted-foreground italic">Chưa có cuộc trò chuyện nào</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {conversations.map((conv) => (
                  <li key={conv.id} className="group relative flex items-center">
                    <button
                      onClick={() => onSelectConversation(conv.id)}
                      className={cn(
                        "flex w-full items-start gap-2.5 rounded-lg px-3 py-2.5 text-left transition-colors pr-8",
                        activeConversation === conv.id
                          ? "bg-sidebar-accent text-sidebar-accent-foreground"
                          : "hover:bg-sidebar-accent/60",
                      )}
                    >
                      <MessageSquare className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{conv.title}</span>
                        <span className="block truncate text-xs text-muted-foreground">{conv.preview}</span>
                      </span>
                    </button>
                    {onDeleteConversation && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onDeleteConversation(conv.id)
                        }}
                        title="Xóa hội thoại"
                        className="absolute right-2 text-muted-foreground opacity-0 hover:text-destructive group-hover:opacity-100 transition-opacity p-1"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </aside>
    </>
  )
}

