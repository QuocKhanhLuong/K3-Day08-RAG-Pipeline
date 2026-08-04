import { NextResponse } from "next/server"

export async function POST(req: Request) {
  try {
    const { query, top_k = 5 } = await req.json()

    if (!query || typeof query !== "string") {
      return NextResponse.json({ error: "Query parameter is required" }, { status: 400 })
    }

    // Call Python FastAPI server (running on port 8000)
    const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8000"
    
    const response = await fetch(`${backendUrl}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k }),
    })

    if (!response.ok) {
      const errorText = await response.text()
      return NextResponse.json(
        { error: `Backend service error: ${response.statusText}`, details: errorText },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error: any) {
    console.error("Error connecting to backend API:", error)
    return NextResponse.json(
      { error: "Could not connect to Python RAG Backend service.", details: error.message },
      { status: 500 }
    )
  }
}
