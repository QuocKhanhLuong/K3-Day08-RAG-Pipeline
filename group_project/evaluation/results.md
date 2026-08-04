# RAG Evaluation Results

- Framework: **RAGAS 0.1.21**
- Số câu hỏi: **15**
- Thời điểm chạy: **2026-08-04T23:23:17+07:00**

## So sánh cấu hình

| Metric | Config A (top_k=3) | Config B (top_k=5) | Δ (Config B (top_k=5) - Config A (top_k=3)) |
|---|---:|---:|---:|
| faithfulness | 0.2944 | 0.3175 | +0.0230 |
| answer_relevancy | 0.0494 | 0.1872 | +0.1378 |
| context_recall | 0.4889 | 0.6111 | +0.1222 |
| context_precision | 0.8056 | 0.8119 | +0.0063 |
| **Average** | **0.4096** | **0.4819** | **+0.0723** |

## Kết luận

**Config B (top_k=5)** có điểm trung bình cao hơn trên bộ kiểm thử này.

## Chi tiết — Config A (top_k=3)

| # | Question | Faithfulness | Relevancy | Recall | Precision |
|---:|---|---:|---:|---:|---:|
| 1 | Thời gian thử việc tối đa đối với vị trí quản lý doanh nghiệp là bao lâu? | 1.0000 | 0.3656 | 1.0000 | 0.5833 |
| 2 | Công việc yêu cầu trình độ cao đẳng trở lên thì được thử việc tối đa mấy ngày? | 0.0000 | 0.0000 | 0.0000 | 0.3333 |
| 3 | Lương thử việc tối thiểu phải bằng bao nhiêu phần trăm lương của công việc đó? | 0.0000 | 0.0000 | 0.0000 | 1.0000 |
| 4 | Hợp đồng lao động có thời hạn dưới 1 tháng có được thỏa thuận thử việc không? | 0.7500 | 0.0000 | 1.0000 | 0.5833 |
| 5 | Khi kết thúc thử việc mà đạt yêu cầu thì người sử dụng lao động phải làm gì? | 0.0000 | 0.0000 | 0.0000 | 1.0000 |
| 6 | Có những loại hợp đồng lao động nào theo Bộ luật Lao động 2019? | 0.0000 | 0.0000 | 1.0000 | 0.8333 |
| 7 | Hợp đồng lao động điện tử có giá trị như hợp đồng giấy không? | 0.0000 | 0.0000 | 0.0000 | 0.8333 |
| 8 | Người lao động làm hợp đồng không xác định thời hạn muốn nghỉ việc phải báo trước bao lâu? | 1.0000 | 0.0000 | 1.0000 | 1.0000 |
| 9 | Người lao động ký hợp đồng từ 12 tháng đến 36 tháng muốn nghỉ việc thì phải báo trước mấy ngày? | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| 10 | Trường hợp nào người lao động được nghỉ việc không cần báo trước? | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| 11 | Người sử dụng lao động đơn phương chấm dứt hợp đồng không xác định thời hạn phải báo trước bao lâu? | 0.6667 | 0.0000 | 0.5000 | 1.0000 |
| 12 | Sau khi chấm dứt hợp đồng lao động, công ty phải thanh toán các khoản liên quan trong bao lâu? | 0.0000 | 0.0000 | 0.5000 | 1.0000 |
| 13 | Điều kiện để người lao động được hưởng trợ cấp thôi việc là gì? | 1.0000 | 0.3752 | 0.3333 | 1.0000 |
| 14 | Công ty chậm trả lương cho nhân viên thì có phải trả thêm tiền không? | 0.0000 | 0.0000 | 0.0000 | 0.5833 |
| 15 | Từ ngày 01/01/2026, mức lương tối thiểu tháng vùng I là bao nhiêu? | 0.0000 | 0.0000 | 0.0000 | 0.3333 |

## Chi tiết — Config B (top_k=5)

| # | Question | Faithfulness | Relevancy | Recall | Precision |
|---:|---|---:|---:|---:|---:|
| 1 | Thời gian thử việc tối đa đối với vị trí quản lý doanh nghiệp là bao lâu? | 1.0000 | 0.3638 | 1.0000 | 0.5833 |
| 2 | Công việc yêu cầu trình độ cao đẳng trở lên thì được thử việc tối đa mấy ngày? | 0.0000 | 0.0000 | 0.0000 | 0.7556 |
| 3 | Lương thử việc tối thiểu phải bằng bao nhiêu phần trăm lương của công việc đó? | 0.0000 | 0.0000 | 1.0000 | 0.7000 |
| 4 | Hợp đồng lao động có thời hạn dưới 1 tháng có được thỏa thuận thử việc không? | 0.0000 | 0.4505 | 1.0000 | 0.6792 |
| 5 | Khi kết thúc thử việc mà đạt yêu cầu thì người sử dụng lao động phải làm gì? | 0.0000 | 0.0000 | 0.0000 | 1.0000 |
| 6 | Có những loại hợp đồng lao động nào theo Bộ luật Lao động 2019? | 0.0000 | 0.0000 | 1.0000 | 0.8056 |
| 7 | Hợp đồng lao động điện tử có giá trị như hợp đồng giấy không? | 0.0000 | 0.2934 | 1.0000 | 0.8042 |
| 8 | Người lao động làm hợp đồng không xác định thời hạn muốn nghỉ việc phải báo trước bao lâu? | 1.0000 | 0.0000 | 1.0000 | 1.0000 |
| 9 | Người lao động ký hợp đồng từ 12 tháng đến 36 tháng muốn nghỉ việc thì phải báo trước mấy ngày? | 0.6667 | 0.4891 | 1.0000 | 1.0000 |
| 10 | Trường hợp nào người lao động được nghỉ việc không cần báo trước? | 1.0000 | 0.4456 | 1.0000 | 1.0000 |
| 11 | Người sử dụng lao động đơn phương chấm dứt hợp đồng không xác định thời hạn phải báo trước bao lâu? | 0.0000 | 0.0000 | 0.0000 | 0.8875 |
| 12 | Sau khi chấm dứt hợp đồng lao động, công ty phải thanh toán các khoản liên quan trong bao lâu? | 0.4286 | 0.3614 | 0.5000 | 0.9167 |
| 13 | Điều kiện để người lao động được hưởng trợ cấp thôi việc là gì? | 0.6667 | 0.4045 | 0.6667 | 1.0000 |
| 14 | Công ty chậm trả lương cho nhân viên thì có phải trả thêm tiền không? | 0.0000 | 0.0000 | 0.0000 | 0.6792 |
| 15 | Từ ngày 01/01/2026, mức lương tối thiểu tháng vùng I là bao nhiêu? | 0.0000 | 0.0000 | 0.0000 | 0.3667 |
