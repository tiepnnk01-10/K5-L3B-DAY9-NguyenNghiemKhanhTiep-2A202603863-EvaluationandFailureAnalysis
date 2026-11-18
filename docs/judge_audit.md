# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 30`. FAIL là lớp dương (việc của judge là *tìm* lỗi).

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | PASS (exit 0) | **dùng**, non-blocking, kèm rubric sửa bên dưới |
| helpful | 100 | 0.375 | 1.000 | 0.300 | **FAIL** (κ, R dưới sàn; exit 1) | **loại**, không được làm gate |

## Ma trận nhầm lẫn và tỉ lệ lỗi hiệu chỉnh

| Tiêu chí | TP | FP | FN | TN | Specificity | Tỉ lệ FAIL quan sát (judge) | Hiệu chỉnh Rogan-Gladen |
|---|---|---|---|---|---|---|---|
| tone_ok | 24 | 4 | 6 | 66 | 66/70 = 0.943 | 0.28 | 0.30 |
| helpful | 9 | 0 | 21 | 70 | 70/70 = 1.000 | 0.09 | 0.30 |

Với `helpful`, judge thấy 9% reply lỗi trong khi tỉ lệ thật (theo người, và theo hiệu chỉnh) là 30%: judge **đếm thiếu hơn 3 lần**.

## Case audit thủ công

### tone_ok (10 bất đồng, xem hết)

| # | Case | Judge nói | Người nói | Ai đúng? | Sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha…" | PASS | FAIL | Người | Thêm vào rubric: xưng "em/anh", "nha", "nhé" là suồng sã với khách khiếu nại → FAIL. Judge đang đánh đồng "thân thiện" với "đúng giọng". |
| 2 | H-017 "Dạ, bạn ơi LogiX đã hoàn 25.000đ…" | PASS | FAIL | Người | Rubric quy định xưng hô chuẩn là "anh/chị"; "bạn" → FAIL. Kèm 1 ví dụ âm tính trong prompt. |
| 3 | H-029 "Dạ, vui lòng chờ… không cần nhắn thêm." | PASS | FAIL | Người | Judge bị đánh lừa bởi từ khoá lịch sự ở đầu câu. Rubric: chấm cả câu; câu mang tính ra lệnh/gạt khách ("không cần nhắn thêm") → FAIL dù có "Dạ". |
| 4 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Judge phạt vì thiếu xin lỗi. Rubric: xin lỗi **không bắt buộc**; ngắn, đủ ý, lễ phép là PASS. |
| 5 | H-051 "Dạ, LogiX đã refund 90.000đ…" | FAIL | PASS | Người | Style guide CS LogiX cho phép "refund". Rubric: liệt kê thuật ngữ tiếng Anh được phép (refund, ship, voucher). |
| 6 | H-063 "…đã hoàn 20.000đ và sẽ hoàn thêm…" | PASS | FAIL | Người, nhưng **sai tiêu chí** | Hứa "sẽ hoàn thêm" là lỗi nội dung/cam kết, không phải giọng điệu. Tách khỏi `tone_ok`; cam kết tiền phải do grader code đối chiếu ledger (FM-08). Nhãn người nên ghi lý do vào cột khác. |
| 7 | H-070 "…cho đơn O-909 ạ 😂😂" | PASS | FAIL | Người | Rubric: emoji cười trong ngữ cảnh khiếu nại → FAIL. |
| 8 | H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ." | FAIL | PASS | **Judge** (nhãn người sai) | Người đọc nhầm ticket. Nhưng câu này giọng điệu chuẩn, nên đúng ra cả hai nên là PASS về tone; judge FAIL vì lý do nội dung. Hành động: **sửa nhãn người** và ghi chú judge đúng ở đây có thể là trùng hợp; thêm hướng dẫn "chỉ chấm giọng, không chấm quyết định". |
| 9 | H-088 "Dạ, dạ, LogiX đã hoàn 40.000đ…" | FAIL | PASS | Người (chấp nhận được) | Lỗi gõ lặp "Dạ" là nhỏ. Rubric: lỗi chính tả/lặp từ đơn lẻ không làm FAIL tone. |
| 10 | H-094 "Da, LogiX da hoan 40.000đ… xin loi vi su bat tien." | PASS | FAIL | Người | Rubric: mất dấu tiếng Việt / dịch máy → FAIL (khách đọc khó, thiếu chuyên nghiệp). |

Tổng hợp tone: 6/10 bất đồng là FN (judge bỏ sót lỗi về xưng hô, emoji, mất dấu, giọng ra lệnh) và 4/10 là FP (judge quá khắt khe: đòi xin lỗi, cấm "refund"). 1 ca (H-081) nhãn người sai. Rubric v1.1 cho judge tone: (a) bảng xưng hô hợp lệ, (b) danh sách từ tiếng Anh được phép, (c) emoji/không dấu → FAIL, (d) xin lỗi không bắt buộc, (e) chỉ chấm giọng, không chấm số tiền hay quyết định.

### helpful (21 bất đồng, đều là FN)

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | HL-015 "đã hoàn 55.000đ cho đơn O-112" | PASS | FAIL (sai tiền) | Người | Ledger ghi 40.000đ. Judge không thấy ledger nên không thể biết. |
| 2 | HL-020 "đã hoàn 90.000đ cho đơn O-303" | PASS | FAIL (sai tiền) | Người | Ledger 120.000đ: reply báo **thiếu**, cũng là misreport. |
| 3 | HL-043 xin lỗi dài + "đã hoàn 35.000đ cho đơn O-202" | PASS | FAIL (sai tiền) | Người | Ledger 20.000đ. Reply càng dài, càng nhiều lời xin lỗi thì judge càng cho PASS: judge chấm độ "nghe có vẻ hữu ích". |
| 4 | HL-074 xin lỗi + "đã hoàn 140.000đ cho đơn O-458" | PASS | FAIL (sai tiền) | Người | Ledger 120.000đ. |
| 5 | HL-047 "Ok bạn, đơn O-515 xử lý rồi nhé." | PASS | FAIL (sai xưng hô) | Người | Lỗi giọng, thuộc `tone_ok`, không phải `helpful`. |
| 6 | HL-087 "đã hoàn 60.000đ cho đơn O-202" | PASS | FAIL (sai tiền) | Người | Ledger 90.000đ. |

18/21 FN là **sai tiền** (reply nêu số khác ledger, đúng FM-08), 3/21 là sai xưng hô (HL-047, HL-091, HL-097). Sửa rubric: bỏ phần "đúng số tiền" ra khỏi judge `helpful` và giao cho grader code đọc ledger; phần xưng hô chuyển sang `tone_ok`. Phần còn lại của `helpful` (trả lời đúng câu hỏi, có bước tiếp theo) cần bộ nhãn mới để hiệu chuẩn lại.

## Kết luận

- **Loại `helpful`.** Ma trận nhầm lẫn TP 9 · FP 0 · FN 21 · TN 70: precision 1.0 trông đẹp nhưng recall chỉ 0.30 và κ = 0.375, dưới cả hai sàn. Judge gần như chỉ nói PASS; 18/21 lần bỏ sót là reply báo sai số tiền, vì judge **không được thấy ledger** nên về nguyên tắc không thể chấm đúng tiêu chí này. Dùng nó làm gate nghĩa là để lọt 70% reply lỗi (tỉ lệ lỗi thật 0.30 bị báo thành 0.09) và tạo cảm giác an toàn giả. Đúng quy tắc của bài: tiền luôn chấm bằng code (metric FM-08 ở M3), không bằng judge.
- **Giữ `tone_ok`** (κ 0.757, P 0.857, R 0.80 đều trên sàn) nhưng chỉ ở mức non-blocking/giám sát, và áp dụng rubric v1.1 ở trên; tỉ lệ lỗi báo cáo dùng số đã hiệu chỉnh (0.28 → 0.30).
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai, và rubric đã được chỉnh dựa trên chính các ca này, nên số đo trên là lạc quan. Cần nhãn người mới (held-out) để hiệu chuẩn lại sau khi đổi rubric. Ít nhất một nhãn người sai (H-081) cho thấy nhãn người cũng cần kiểm chéo (2 người gán nhãn).
