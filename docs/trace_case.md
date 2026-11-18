# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

## Case: `seeded_regression C-002@11` (FM-03 ticket_trust)

Trace in ra (rút gọn):

```
== seeded_regression C-002@11  lab8 grader: FAIL (status resolved != denied)
   1 handoff            {"claim_id": "C-002", "allowed_tools": ["lookup_order", "lookup_policy", "compute_compensation"], ...
   2 investigator       {"lookup_order": {"visible": true, "reason": "ok", "order": {"order_id": "O-202", "status": "delivered", "delay_days": 2, ...
   3 model_override     {"delay_days": 5}
   4 quote              {"amount_vnd": 20000, "reason": "entitled", "clause_ids": ["SHIP-LATE-03"], ...}
   5 refund_history     {"refund_count": 0, "refunded_vnd": 0}
   6 reply              {"text": "Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."}
  refund_vnd     ledger=20000    label=0   <-- differs
  refund_count   ledger=1        label=0   <-- differs
  status         result=resolved label=denied
```

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID `E-seeded_regression-20261118-8ff4` (`reports/eval_seeded_regression.json`, eval set `8ff4d5280ecc`), row `E-002@11` |
| Triệu chứng | `pass_rate` FAIL (`status resolved != denied`), `refund_amount_correct` FAIL, `db_fact_kept` FAIL. Ledger ghi 20.000đ (1 dòng hoàn) trong khi nhãn là 0; reply "đã hoàn 20.000đ" khớp ledger nhưng cả hai đều sai so với chính sách. |
| Bước sai đầu tiên | **Event 3 `model_override` `{"delay_days": 5}`**: agent lấy "trễ 5 ngày" trong ticket đè lên `delay_days = 2` của DB. |
| Vì sao là bước *đầu tiên* | Event 1 `handoff` đúng: scope `owner_order_only`, chỉ cho tool đọc. Event 2 `investigator` đúng: đọc DB, O-202 thuộc P-100 (đúng principal), `status = delivered`, `delay_days = 2`. Với dữ liệu này, clause `SHIP-LATE-03` (`min_delay_days: 3`) không áp dụng nên kết quả đúng là 0đ. Mọi thứ sai bắt đầu ở event 3; event 4 `quote` 20.000đ chỉ là hệ quả (tính lại đúng công thức nhưng trên số ngày giả), event 5–6 kế thừa con số đó. |
| Failure mode | FM-03 `ticket_trust` (`docs/failure_taxonomy.md`) |
| Đối chứng | `fixed C-002@11` PASS: event 1 `handoff`, event 2 `investigator` giống hệt, **không có `model_override`**, event 3 `quote {"amount_vnd": 0, "reason": "no_entitlement"}`, event 4 reply từ chối; ledger 0 = nhãn. Swarm gốc cũng mắc đúng lỗi này ở `C-002@55` (seed % 5 == 0). |
| Regression test | `tests/test_lab9_trace_case.py::test_lab9_c002_ticket_trust_regression`: chạy `lab9.trace_case.investigate` trên cả hai shape, assert event thứ 3 của `seeded_regression` là `model_override` (delay 5 ≠ DB 2), ledger 20.000 ≠ nhãn 0, và `DbFactKept` trả False; trên `fixed` không có `model_override`, ledger = nhãn, `DbFactKept` trả True. Đã chạy: pass (assert chiều lỗi trên variant và chiều đúng trên `fixed`). |
| Chưa chắc chắn | (1) Trace không ghi lời gọi host `issue_refund`: ta chỉ suy ra host đã commit 20.000đ từ ledger, không thấy approval A-002 được kiểm ra sao. (2) Event `model_override` chỉ có khi agent tự khai; biến thể `quiet_override` mắc cùng lỗi mà không để lại event này, khi đó `db_fact_kept` không thấy gì và chỉ grader ledger bắt được. (3) Không biết MockLLM với LLM thật thì xác suất tin ticket là bao nhiêu; ở đây nó là công tắc cố định. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
