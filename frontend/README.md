# Chatbot Legal System — Frontend UI

Đây là phần giao diện (Frontend) của ứng dụng **Trợ lý Hỏi Đáp Luật Lao Động**, được xây dựng bằng **Next.js (App Router)**, **React 19**, **Tailwind CSS v4**, và **Lucide Icons**.

## Cấu trúc thư mục

```
frontend/
├── app/                  # Trang chính, layout và style toàn cục
│   ├── globals.css       # Tailwind CSS & CSS variables
│   ├── layout.tsx        # Layout chính & Google Fonts
│   └── page.tsx          # Giao diện chat hỏi đáp chính
├── components/           # Các linh kiện UI chính
│   ├── app-sidebar.tsx   # Thanh bên (danh sách đoạn chat & gợi ý chủ đề)
│   ├── chat-input.tsx    # Ô nhập tin nhắn & nút gửi
│   ├── citation-card.tsx # Hiển thị căn cứ pháp lý / điều luật
│   ├── message-bubble.tsx# Bong bóng tin nhắn user / trợ lý / typing
│   ├── welcome-screen.tsx# Màn hình chào mừng & câu hỏi gợi ý
│   └── ui/               # UI Primitive (button)
├── lib/                  # Helper logic & dữ liệu mock
│   ├── mock-answer.ts    # Logic sinh câu trả lời tự động cho demo
│   ├── mock-data.ts      # Dữ liệu hội thoại mẫu & các điều luật
│   └── utils.ts          # Utility classes (cn)
├── public/               # Favicon & icons
├── components.json       # Cấu hình shadcn/ui
├── next.config.mjs       # Cấu hình Next.js
├── postcss.config.mjs    # Cấu hình PostCSS / Tailwind CSS
├── tsconfig.json         # Cấu hình TypeScript
└── package.json          # Danh sách thư viện phụ thuộc
```

## Hướng dẫn cài đặt & Chạy giao diện

1. Di chuyển vào thư mục `frontend`:
   ```bash
   cd frontend
   ```

2. Cài đặt thư viện phụ thuộc:
   ```bash
   npm install
   ```

3. Khởi chạy máy chủ phát triển (Development Server):
   ```bash
   npm run dev
   ```

4. Truy cập địa chỉ: `http://localhost:3000`

---
*Ghi chú: Bạn có thể copy nguyên thư mục `frontend` này sang bất kỳ dự án hoặc folder khác để chạy độc lập.*
