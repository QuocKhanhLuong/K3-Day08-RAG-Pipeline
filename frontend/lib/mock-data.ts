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
  retrieval_source?: string
  retrieval_log?: any
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
  { id: "thu-viec", label: "Thời gian & Lương thử việc", icon: Briefcase },
  { id: "ot", label: "Làm thêm giờ (OT)", icon: Clock },
  { id: "nghi-phep", label: "Nghỉ phép năm & Tiền bồi dưỡng", icon: CalendarDays },
  { id: "hop-dong", label: "Hợp đồng lao động", icon: FileSignature },
  { id: "sa-thai", label: "Đơn phương chấm dứt HĐLĐ", icon: UserX },
  { id: "luong", label: "Lương tối thiểu & Chậm trả lương", icon: Wallet },
  { id: "quyen-loi", label: "Quyền lợi người lao động", icon: GraduationCap },
  { id: "bhxh", label: "Bảo hiểm xã hội & xử phạt", icon: ShieldCheck },
]

export const suggestedQuestions: string[] = [
  "Không nghỉ hết phép năm có được thanh toán tiền?",
  "Thời gian thử việc, tiền lương và bảo hiểm xã hội quy định như thế nào?",
  "Khi nào doanh nghiệp được đăng ký tăng giờ làm thêm?",
  "Chậm trả lương do bất khả kháng: Doanh nghiệp được trễ bao lâu?",
  "Thế nào là đơn phương chấm dứt hợp đồng lao động đúng luật?",
  "Điểm mới Bộ luật Lao động 2019: Quyền lợi người lao động cần biết",
]

export const conversations: Conversation[] = []

