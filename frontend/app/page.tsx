"use client"

import { useEffect, useRef, useState } from "react"
import { PanelLeft, Scale, Globe } from "lucide-react"

import { AppSidebar } from "@/components/app-sidebar"
import { WelcomeScreen } from "@/components/welcome-screen"
import { ChatInput } from "@/components/chat-input"
import { MessageBubble, TypingBubble } from "@/components/message-bubble"
import { CrawlModal } from "@/components/crawl-modal"
import { suggestedQuestions as defaultQuestions, type Conversation, type Message } from "@/lib/mock-data"
import { getMockAnswer } from "@/lib/mock-answer"

const STORAGE_KEY = "legal_rag_conversations_v1"

export default function Page() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [crawlModalOpen, setCrawlModalOpen] = useState(false)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [typing, setTyping] = useState(false)
  const [guidanceQueries, setGuidanceQueries] = useState<string[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)

  // Load conversations from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed: Conversation[] = JSON.parse(saved)
        setConversations(parsed)
      }
    } catch (e) {
      console.error("Failed to load conversations from localStorage:", e)
    }
  }, [])

  // Save conversations to localStorage whenever they change
  const saveConversations = (updated: Conversation[]) => {
    setConversations(updated)
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
    } catch (e) {
      console.error("Failed to save conversations to localStorage:", e)
    }
  }

  // Fetch guidance queries from backend API
  const fetchQueries = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/guidance-queries")
      if (res.ok) {
        const data = await res.json()
        if (data.queries && data.queries.length > 0) {
          setGuidanceQueries(data.queries)
        }
      }
    } catch (e) {
      // Fallback to default questions if backend is not reachable
    }
  }

  useEffect(() => {
    fetchQueries()
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages, typing])

  const handleSend = async (text: string) => {
    const userMessage: Message = { id: `u-${Date.now()}`, role: "user", content: text }
    const newMessages = [...messages, userMessage]
    setMessages(newMessages)
    setTyping(true)

    // Ensure we have an active conversation ID
    let currentId = activeConversationId

    if (!currentId) {
      currentId = `conv-${Date.now()}`
      setActiveConversationId(currentId)
    }

    try {
      const res = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text, top_k: 5 }),
      })

      let assistantMessage: Message

      if (res.ok) {
        const data = await res.json()
        assistantMessage = {
          id: `a-${Date.now()}`,
          role: "assistant",
          content: data.answer || "Không thể khởi tạo câu trả lời.",
          citations: data.citations || [],
          retrieval_source: data.retrieval_source,
          retrieval_log: data.retrieval_log,
        }

      } else {
        const answer = getMockAnswer(text)
        assistantMessage = { id: `a-${Date.now()}`, role: "assistant", ...answer }
      }

      const updatedMessages = [...newMessages, assistantMessage]
      setMessages(updatedMessages)

      // Save/update conversation entry
      const now = new Date()
      const dateStr = `${now.getHours()}:${String(now.getMinutes()).padStart(2, "0")}`
      const titleStr = text.length > 30 ? text.slice(0, 30) + "..." : text
      const previewStr = assistantMessage.content.slice(0, 45) + "..."

      setConversations((prev) => {
        const existingIdx = prev.findIndex((c) => c.id === currentId)
        if (existingIdx >= 0) {
          const updated = [...prev]
          updated[existingIdx] = {
            ...updated[existingIdx],
            preview: previewStr,
            messages: updatedMessages,
          }
          try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
          } catch (e) {}
          return updated
        } else {
          const newConv: Conversation = {
            id: currentId!,
            title: titleStr,
            preview: previewStr,
            date: dateStr,
            messages: updatedMessages,
          }
          const updated = [newConv, ...prev]
          try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
          } catch (e) {}
          return updated
        }
      })
    } catch (err) {
      console.error("Error calling chat API:", err)
      const answer = getMockAnswer(text)
      const assistantMessage: Message = { id: `a-${Date.now()}`, role: "assistant", ...answer }
      const updatedMessages = [...newMessages, assistantMessage]
      setMessages(updatedMessages)
    } finally {
      setTyping(false)
    }
  }

  const handleSelectConversation = (id: string) => {
    const conv = conversations.find((c) => c.id === id)
    setActiveConversationId(id)
    setSidebarOpen(false)
    if (conv && conv.messages.length > 0) {
      setMessages(conv.messages)
      setTyping(false)
    } else {
      handleNewChat()
    }
  }

  const handleDeleteConversation = (id: string) => {
    const updated = conversations.filter((c) => c.id !== id)
    saveConversations(updated)
    if (activeConversationId === id) {
      handleNewChat()
    }
  }

  const handleNewChat = () => {
    setMessages([])
    setActiveConversationId(null)
    setTyping(false)
    setSidebarOpen(false)
  }

  const hasMessages = messages.length > 0
  const questionsToDisplay = guidanceQueries.length > 0 ? guidanceQueries : defaultQuestions

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      <AppSidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        conversations={conversations}
        activeConversation={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onDeleteConversation={handleDeleteConversation}
        onSelectTopic={(label) => handleSend(`Cho tôi biết các quy định liên quan đến ${label.toLowerCase()}.`)}
        onNewChat={handleNewChat}
        onOpenCrawlModal={() => setCrawlModalOpen(true)}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-border bg-background/80 px-4 py-3 backdrop-blur md:px-6">
          <button
            aria-label="Mở thanh bên"
            onClick={() => setSidebarOpen(true)}
            className="text-muted-foreground md:hidden"
          >
            <PanelLeft className="size-5" />
          </button>
          <div className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground md:hidden">
              <Scale className="size-4" />
            </span>
            <div className="leading-tight">
              <h1 className="text-sm font-semibold text-foreground">Trợ lý Luật Lao Động</h1>
              <p className="text-xs text-muted-foreground">Bộ luật Lao động 2019 &amp; các văn bản pháp luật</p>
            </div>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={() => setCrawlModalOpen(true)}
              className="flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-foreground transition-colors hover:border-primary hover:text-primary"
            >
              <Globe className="size-3.5 text-primary" />
              <span className="hidden sm:inline">Nạp dữ liệu từ URL</span>
            </button>
            <span className="hidden items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground md:flex">
              <span className="size-1.5 rounded-full bg-emerald-500" />
              Hệ thống sẵn sàng
            </span>
          </div>
        </header>

        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          {hasMessages ? (
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-6 md:px-6">
              {messages.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
              {typing && <TypingBubble />}
            </div>
          ) : (
            <WelcomeScreen onPick={handleSend} questions={questionsToDisplay} />
          )}
        </div>

        <ChatInput onSend={handleSend} disabled={typing} />
      </main>

      <CrawlModal
        open={crawlModalOpen}
        onClose={() => setCrawlModalOpen(false)}
        onSuccess={fetchQueries}
      />
    </div>
  )
}


