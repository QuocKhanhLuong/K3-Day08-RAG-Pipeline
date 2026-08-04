import type { Citation } from "./mock-data"

type Answer = { content: string; citations?: Citation[] }

const KNOWLEDGE: { keywords: string[]; answer: Answer }[] = [
  {
    keywords: ["thử việc", "thu viec", "probation"],
    answer: {
      content:
        "Với các vị trí cần trình độ chuyên môn kỹ thuật từ cao đẳng trở lên (ví dụ lập trình viên), quy định như sau:\n\n• Thời gian thử việc tối đa: 60 ngày.\n• Lương thử việc: do hai bên thỏa thuận nhưng ít nhất bằng 85% mức lương của công việc chính thức.\n\nMỗi công việc chỉ được thử việc 01 lần. Trong thời gian thử việc, mỗi bên có quyền hủy thỏa thuận mà không cần báo trước và không phải bồi thường.",
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
  },
  {
    keywords: ["sa thải", "sa thai", "zalo", "báo trước", "bao truoc", "nghỉ việc", "đơn phương"],
    answer: {
      content:
        "Việc sa thải qua tin nhắn Zalo mà không báo trước 30 ngày thường là trái luật.\n\n• Người sử dụng lao động chỉ được đơn phương chấm dứt hợp đồng trong các trường hợp luật cho phép, và phải báo trước ít nhất 30 ngày với hợp đồng xác định thời hạn (ít nhất 45 ngày với hợp đồng không xác định thời hạn).\n• 'Sa thải' là hình thức kỷ luật, chỉ áp dụng cho một số vi phạm cụ thể và phải tuân thủ trình tự xử lý kỷ luật (có cuộc họp, biên bản...).\n\nNhắn tin Zalo không đáp ứng yêu cầu về hình thức và trình tự, nên bạn có quyền khiếu nại hoặc khởi kiện đòi quyền lợi.",
      citations: [
        {
          source: "Bộ luật Lao động 2019",
          article: "Điều 36 — Đơn phương chấm dứt HĐLĐ",
          excerpt:
            "Người sử dụng lao động phải báo trước ít nhất 30 ngày đối với hợp đồng lao động xác định thời hạn từ 12 đến 36 tháng.",
        },
        {
          source: "Bộ luật Lao động 2019",
          article: "Điều 122 — Nguyên tắc xử lý kỷ luật lao động",
          excerpt:
            "Việc xử lý kỷ luật lao động phải có sự tham gia của tổ chức đại diện người lao động và được lập thành biên bản.",
        },
      ],
    },
  },
  {
    keywords: ["nghỉ phép", "nghi phep", "phép năm", "annual leave"],
    answer: {
      content:
        "Người lao động làm việc đủ 12 tháng cho một người sử dụng lao động được nghỉ hằng năm hưởng nguyên lương theo hợp đồng:\n\n• 12 ngày với điều kiện làm việc bình thường.\n• 14 ngày với người chưa thành niên, người khuyết tật, hoặc công việc nặng nhọc, độc hại.\n• 16 ngày với công việc đặc biệt nặng nhọc, độc hại, nguy hiểm.\n\nCứ mỗi 5 năm làm việc cho cùng một người sử dụng lao động, số ngày nghỉ phép năm được cộng thêm 01 ngày.",
      citations: [
        {
          source: "Bộ luật Lao động 2019",
          article: "Điều 113 — Nghỉ hằng năm",
          excerpt:
            "Người lao động làm đủ 12 tháng được nghỉ hằng năm hưởng nguyên lương: 12, 14 hoặc 16 ngày tùy điều kiện công việc.",
        },
        {
          source: "Bộ luật Lao động 2019",
          article: "Điều 114 — Ngày nghỉ hằng năm tăng theo thâm niên",
          excerpt: "Cứ đủ 05 năm làm việc cho một người sử dụng lao động thì số ngày nghỉ hằng năm được tăng thêm 01 ngày.",
        },
      ],
    },
  },
  {
    keywords: ["làm thêm", "lam them", "ot", "tăng ca", "tang ca", "ban đêm", "overtime"],
    answer: {
      content:
        "Tiền lương làm thêm giờ được tính theo đơn giá tiền lương của công việc đang làm:\n\n• Ngày thường: ít nhất 150%.\n• Ngày nghỉ hằng tuần: ít nhất 200%.\n• Ngày lễ, Tết, ngày nghỉ có hưởng lương: ít nhất 300% (chưa kể tiền lương ngày lễ với người hưởng lương ngày).\n\nNếu làm thêm vào ban đêm, ngoài các mức trên, người lao động còn được trả thêm ít nhất 30% lương ban đêm và thêm 20% tiền lương của công việc làm vào ban ngày.",
      citations: [
        {
          source: "Bộ luật Lao động 2019",
          article: "Điều 98 — Tiền lương làm thêm giờ, làm việc ban đêm",
          excerpt:
            "Làm thêm giờ được trả ít nhất 150% ngày thường, 200% ngày nghỉ tuần, 300% ngày lễ; làm ban đêm được trả thêm ít nhất 30%.",
        },
      ],
    },
  },
  {
    keywords: ["hợp đồng", "hop dong", "hđlđ", "học việc", "hoc viec"],
    answer: {
      content:
        "Hợp đồng lao động phải được giao kết bằng văn bản (trừ một số trường hợp dưới 01 tháng có thể bằng lời nói) và gồm hai loại: xác định thời hạn (tối đa 36 tháng) và không xác định thời hạn.\n\nVới học nghề, tập nghề: người sử dụng lao động phải ký hợp đồng đào tạo, không được thu học phí và nếu người học trực tiếp tạo ra sản phẩm hợp quy cách thì phải được trả lương theo mức hai bên thỏa thuận.",
      citations: [
        {
          source: "Bộ luật Lao động 2019",
          article: "Điều 20 — Loại hợp đồng lao động",
          excerpt: "Hợp đồng lao động gồm loại không xác định thời hạn và loại xác định thời hạn (không quá 36 tháng).",
        },
        {
          source: "Bộ luật Lao động 2019",
          article: "Điều 61, 62 — Học nghề, tập nghề & hợp đồng đào tạo",
          excerpt:
            "Người sử dụng lao động không được thu học phí; nếu người học nghề trực tiếp làm ra sản phẩm hợp quy cách thì được trả lương.",
        },
      ],
    },
  },
]

const DEFAULT_ANSWER: Answer = {
  content:
    "Đây là bản demo giao diện nên câu trả lời được lấy từ dữ liệu mẫu. Bạn hãy thử các chủ đề như thử việc, làm thêm giờ (OT), nghỉ phép, hợp đồng lao động hoặc sa thải để xem câu trả lời kèm căn cứ pháp lý.\n\nKhi kết nối AI thật, trợ lý sẽ tra cứu trực tiếp Bộ luật Lao động 2019 và các nghị định hướng dẫn để trả lời câu hỏi của bạn.",
}

export function getMockAnswer(question: string): Answer {
  const normalized = question.toLowerCase()
  for (const entry of KNOWLEDGE) {
    if (entry.keywords.some((k) => normalized.includes(k))) {
      return entry.answer
    }
  }
  return DEFAULT_ANSWER
}
