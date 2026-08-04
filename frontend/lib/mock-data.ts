import type { LucideIcon } from "lucide-react"
import {
  Briefcase,
  Clock,
  CalendarDays,
  FileSignature,
  UserX,
  Wallet,
  GraduationCap,
  ShieldCheck,
} from "lucide-react"

export type Citation = {
  source: string
  article: string
  excerpt: string
}

export type Message = {
  id: string
  role: "user" | "assistant"
  content: string
  citations?: Citation[]
}

export type Conversation = {
  id: string
  title: string
  preview: string
  date: string
  messages: Message[]
}

export type Topic = {
  id: string
  label: string
  icon: LucideIcon
}

export const topics: Topic[] = [
  { id: "thu-viec", label: "Thử việc", icon: Briefcase },
  { id: "ot", label: "Làm thêm giờ (OT)", icon: Clock },
  { id: "nghi-phep", label: "Nghỉ phép", icon: CalendarDays },
  { id: "hop-dong", label: "Hợp đồng lao động", icon: FileSignature },
  { id: "sa-thai", label: "Sa thải & thôi việc", icon: UserX },
  { id: "luong", label: "Lương & phụ cấp", icon: Wallet },
  { id: "hoc-viec", label: "Hợp đồng học việc", icon: GraduationCap },
  { id: "bhxh", label: "BHXH & quyền lợi", icon: ShieldCheck },
]

export const suggestedQuestions: string[] = [
  "Thời gian thử việc tối đa cho vị trí lập trình viên là bao lâu và lương thử việc tối thiểu bằng bao nhiêu % lương chính thức?",
  "Công ty sa thải tôi qua tin nhắn Zalo mà không báo trước 30 ngày thì có đúng luật không?",
  "Một năm tôi được nghỉ phép có hưởng lương bao nhiêu ngày?",
  "Làm thêm giờ ban đêm được trả lương như thế nào?",
]

export const conversations: Conversation[] = [
  {
    id: "c1",
    title: "Thời gian & lương thử việc",
    preview: "Thời gian thử việc tối đa cho lập trình viên...",
    date: "Hôm nay",
    messages: [
      {
        id: "m1",
        role: "user",
        content:
          "Thời gian thử việc tối đa cho vị trí lập trình viên là bao lâu và lương thử việc tối thiểu bằng bao nhiêu % lương chính thức?",
      },
      {
        id: "m2",
        role: "assistant",
        content:
          "Vị trí lập trình viên thường yêu cầu trình độ từ cao đẳng, đại học trở lên nên được xếp vào nhóm công việc có chức danh nghề cần trình độ chuyên môn kỹ thuật.\n\nVì vậy:\n\n• Thời gian thử việc tối đa là 60 ngày.\n• Tiền lương thử việc do hai bên thỏa thuận nhưng ít nhất phải bằng 85% mức lương của công việc chính thức.\n\nLưu ý: mỗi công việc chỉ được thử việc 01 lần, và trong thời gian thử việc mỗi bên đều có quyền hủy thỏa thuận mà không cần báo trước, không phải bồi thường.",
        citations: [
          {
            source: "Bộ luật Lao động 2019",
            article: "Điều 25 — Thời gian thử việc",
            excerpt:
              "Không quá 60 ngày đối với công việc có chức danh nghề nghiệp cần trình độ chuyên môn, kỹ thuật từ cao đẳng trở lên.",
          },
          {
            source: "Bộ luật Lao động 2019",
            article: "Điều 26 — Tiền lương thử việc",
            excerpt:
              "Tiền lương của người lao động trong thời gian thử việc do hai bên thỏa thuận nhưng ít nhất phải bằng 85% mức lương của công việc đó.",
          },
        ],
      },
    ],
  },
  {
    id: "c2",
    title: "Sa thải qua tin nhắn Zalo",
    preview: "Công ty sa thải tôi qua Zalo không báo trước...",
    date: "Hôm qua",
    messages: [],
  },
  {
    id: "c3",
    title: "Số ngày nghỉ phép năm",
    preview: "Một năm được nghỉ phép hưởng lương bao nhiêu...",
    date: "3 ngày trước",
    messages: [],
  },
  {
    id: "c4",
    title: "Lương làm thêm giờ ban đêm",
    preview: "Cách tính lương OT ban đêm...",
    date: "Tuần trước",
    messages: [],
  },
]
