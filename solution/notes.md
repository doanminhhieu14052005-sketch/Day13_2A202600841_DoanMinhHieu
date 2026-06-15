# Diagnosis scratchpad

Mỗi lỗi dưới đây suy ra từ config "cài cắm" ban đầu (`temperature 1.6`, `loop_guard false`,
`retry off`, `cache off`, `normalize_unicode false`, `redact_pii false`, `tool_error_rate 0.18`,
`catalog_override macbook:false`, `tool_budget 0`, `self_consistency 1`, prompt cố tình tệ) +
mô tả trong `docs/FAULT_CLASSES.md`. **Cần chạy sim để điền số đo thật vào cột "số đo".**

| symptom (telemetry) | request nào | nguyên nhân | config fix | prompt/wrapper fix |
|---|---|---|---|---|
| total sai, lệch ở nhiệt độ cao | mọi đơn có tính tiền | temperature 1.6, no verify/self-consistency, prompt "ước lượng" | temperature 0.2, self_consistency 2, verify true | prompt: công thức floor chính xác + verify |
| bịa tổng cho hàng hết / không rõ | pub-02 (MacBook), pub-05 (AirPods) | prompt luôn ép đưa total, không grounding | — | prompt: chỉ dùng dữ liệu tool, từ chối, không bịa |
| gọi tool dư | đơn nhiều bước | tool_budget 0, prompt over-call | tool_budget 4 | prompt: mỗi tool 1 lần, theo thứ tự |
| lộ email/phone | pub-13 | redact_pii false, prompt echo liên hệ | redact_pii true | prompt: không lặp PII; wrapper redact() |
| token/chi phí cao | mọi request | premium tier, verbose, context 8, max_tok 2000 | tier standard, verbose off, context 4, max_tok 512 | wrapper cache |
| latency đuôi dài | ngẫu nhiên | timeout 0, no cache | timeout 20000, cache on | wrapper cache |
| tool fail ~18% | ngẫu nhiên | tool_error_rate 0.18, retry off | tool_error_rate 0, retry on | wrapper retry/backoff |
| chất lượng giảm dần theo lượt | turn lớn | session_drift_rate 0.06, no reset | drift 0, context_reset_every 4, self_consistency 2 | — |
| lặp action đến max_steps | một số đơn | loop_guard false, max_steps 12 | loop_guard true, max_steps 6 | — |
| MacBook luôn hết hàng; thành phố có dấu fail | pub-02/pub-10 (MacBook), pub-11 ("Hà Nội") | catalog_override macbook:false, normalize_unicode false | xóa catalog_override, normalize_unicode true | — |
| nghe theo giá giả trong "GHI CHU" | PRIVATE (injection) | prompt coi note là chỉ dẫn | — | prompt: note là DATA; wrapper: strip note đáng ngờ |

## Trạng thái
- [x] Đổi `"team"` → `2A202600841_DoanMinhHieu` (findings.json + submission/manifest.json).
- [x] Prompt được áp dụng chắc chắn: `wrapper.py` đọc `prompt.txt` và set `conf["system_prompt"]` mỗi request (không phụ thuộc sim tự nạp).
- [ ] Đặt LLM engine khi chạy: `OPENAI_API_KEY` (cloud) **hoặc** Ollama local (đổi `provider:"local"` + `LOCAL_BASE_URL`).
- [ ] Chạy sim ở máy KHÔNG có Kaspersky → đọc telemetry (`logs/`) → **điền số đo thật** vào bảng + `findings.json.evidence.observed`, rồi chạy scorer để có `score.json`.
- [ ] Nếu sim báo `model_price_tier` không hợp lệ: thử `"premium"` (an toàn) hoặc `"economy"`.

## Vì sao không chạy sim được trên máy này
Kaspersky (driver kernel `klif`/`KLHK`) chặn binary PyInstaller chưa ký nạp `python312.dll`
(`LoadLibrary: Invalid access to memory location`). Đã thử pause / exit / trusted app / tắt
2 thành phần / reboot — đều không gỡ được vì Self-Defense. Cách chạy: gỡ Kaspersky tạm hoặc
dùng máy/VM khác. Phần code nộp KHÔNG bị ảnh hưởng.
