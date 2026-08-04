"use client"

import { useEffect, useRef, useState } from "react"
import { PanelLeft, Scale } from "lucide-react"
import { AppSidebar } from "@/components/app-sidebar"
import { WelcomeScreen } from "@/components/welcome-screen"
import { ChatInput } from "@/components/chat-input"
import { MessageBubble, TypingBubble } from "@/components/message-bubble"
import { conversations, type Message } from "@/lib/mock-data"
import { getMockAnswer } from "@/lib/mock-answer"

export default function Page() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [typing, setTyping] = useState(false)
  const [activeConversation, setActiveConversation] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages, typing])

  const handleSend = async (text: string) => {
    const userMessage: Message = { id: `u-${Date.now()}`, role: "user", content: text }
    setMessages((prev) => [...prev, userMessage])
    setActiveConversation(null)
    setTyping(true)

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text, top_k: 5 }),
      })

      if (!res.ok) {
        throw new Error(`HTTP error ${res.status}`)
      }

      const data = await res.json()
      const assistantMessage: Message = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: data.answer || "Không thể khởi tạo câu trả lời.",
        citations: data.citations || [],
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (err) {
      console.error("Error calling chat API:", err)
      const answer = getMockAnswer(text)
      setMessages((prev) => [...prev, { id: `a-${Date.now()}`, role: "assistant", ...answer }])
    } finally {
      setTyping(false)
    }
  }

  const handleSelectConversation = (id: string) => {
    const conv = conversations.find((c) => c.id === id)
    setActiveConversation(id)
    setSidebarOpen(false)
    if (conv && conv.messages.length > 0) {
      setMessages(conv.messages)
      setTyping(false)
    } else {
      handleNewChat()
    }
  }

  const handleNewChat = () => {
    setMessages([])
    setActiveConversation(null)
    setTyping(false)
    setSidebarOpen(false)
  }

  const hasMessages = messages.length > 0

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      <AppSidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        activeConversation={activeConversation}
        onSelectConversation={handleSelectConversation}
        onSelectTopic={(label) => handleSend(`Cho tôi biết các quy định liên quan đến ${label.toLowerCase()}.`)}
        onNewChat={handleNewChat}
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
              <p className="text-xs text-muted-foreground">Bộ luật Lao động 2019 &amp; nghị định hướng dẫn</p>
            </div>
          </div>
          <span className="ml-auto hidden items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground sm:flex">
            <span className="size-1.5 rounded-full bg-chart-3" />
            Bản demo giao diện
          </span>
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
            <WelcomeScreen onPick={handleSend} />
          )}
        </div>

        <ChatInput onSend={handleSend} disabled={typing} />
      </main>
    </div>
  )
}
