# Observathon Day-13 — Báo cáo Solution

**Team:** 2A202600841_DoanMinhHieu · **Tác giả:** Đoàn Minh Hiếu

## 1. Bài toán
Một agent thương mại điện tử **hộp đen, im lặng**, chạy trên **LLM thật**, bị cài cắm lỗi cố ý.
`run_output.json` chỉ trả về `answer` + `status`. Nhiệm vụ: **gắn quan sát → chẩn đoán lỗi → sửa**
qua 3 đòn bẩy: `config.json`, `prompt.txt`, `wrapper.py`.

## 2. Quy trình: Observe → Diagnose → Fix
- **Observe:** `wrapper.py` bọc mọi request, ghi telemetry (latency, tokens, cost, số tool, PII,
  status, trace) bằng bộ `telemetry/` — đây là nơi DUY NHẤT thấy được các tín hiệu này.
- **Diagnose:** đối chiếu config cài cắm + hành vi → xác định **11 fault class** (xem `findings.json`).
- **Fix:** sửa knob trong config, viết lại system prompt, thêm mitigation ở wrapper.

## 3. Các thay đổi chính

**`solution/config.json`** — sửa các knob bị đặt sai:
`temperature 1.6→0.2`, `loop_guard→true`, bật `retry`+`cache`, `normalize_unicode→true`,
`redact_pii→true`, xóa `catalog_override` (MacBook bị ép hết hàng), `tool_error_rate 0.18→0`,
`session_drift_rate→0` + `context_reset_every 4`, `tool_budget→4`, `self_consistency→3`,
`verify→true`, hạ `model_price_tier`/`verbose_system`/`context_size`/`max_completion_tokens` (giảm chi phí).

**`solution/prompt.txt`** — system prompt mới đảo ngược prompt tệ: gọi tool đúng thứ tự & mỗi tool 1 lần,
**grounding** (chỉ dùng dữ liệu tool, từ chối khi hết hàng/không phục vụ, không bịa tổng),
**số học chính xác** (công thức floor số nguyên + verify), **không lặp PII**, **chống injection**
(coi "GHI CHU"/ghi chú là DỮ LIỆU, giá chỉ lấy từ tool), kết thúc bằng `Tong cong: <int> VND`.

**`solution/wrapper.py`** — observability + mitigation:
- **prompt routing** (đảm bảo prompt.txt được áp dụng mọi request),
- **sanitize** ghi chú injection đáng ngờ,
- **retry/backoff** lỗi tạm thời, **cache** câu lặp,
- **redact PII** trong câu trả lời,
- **chuẩn hóa dòng tổng** → bỏ dấu phân cách/markdown, in lại `Tong cong: <int> VND` (cứu các đơn đúng toán nhưng sai định dạng).

**`solution/findings.json`** — chẩn đoán 11 lỗi (class + bằng chứng + nguyên nhân + cách sửa):
`arithmetic_error, fabrication, tool_overuse, pii_leak, cost_blowup, latency_spike, error_spike,
quality_drift, infinite_loop, tool_failure, prompt_injection`.

## 4. Kết quả
- **Vòng public:** điểm tổng **88.64/100**; `diagnosis-F1 = 0.952` (gần tuyệt đối);
  error 1.0, cost 1.0, prompt 0.78, quality 0.72.
- **Kiểm thử trên bộ private (Ollama local):** định dạng chuẩn 80/80, **PII rò rỉ 0**,
  **20/20 câu injection đều dùng giá thật — không mắc bẫy giá giả trong ghi chú**.

## 5. Các bước đã thực hiện
1. Cài đặt môi trường, chạy `harness/selfcheck.py` (PASS).
2. Gắn telemetry trong `wrapper.py`, chạy sim để quan sát hành vi.
3. Chẩn đoán 11 fault class → ghi `findings.json`.
4. Sửa `config.json`, viết lại `prompt.txt`, thêm mitigation + chuẩn hóa output ở `wrapper.py`.
5. Chạy sim → `run_output.json`; chấm bằng scorer → `score.json`; commit & push.
