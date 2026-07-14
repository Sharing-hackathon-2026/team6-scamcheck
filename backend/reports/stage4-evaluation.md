# Báo cáo đánh giá Stage 4

- Thời điểm: 2026-07-14T17:19:40+00:00
- Model: `gemini-3.1-flash-lite`
- Commit: `ffe8a4aff9654e171b58afb8760201300d43e5cf`
- Prompt/pipeline: `baseline=detective-function-call-v2-stage3-scope; improved=detective-function-call-v3-stage4-scope` / `stage4-v1-prompt3`
- Dataset: 60 tin
- Phương pháp: two throttled 60-case runs; baseline Stage 3 prompt vs improved Stage 4 prompt + deterministic rules; no invalid outputs

## Tổng quan

| Metric | Baseline | Improved | Delta |
|---|---:|---:|---:|
| Accuracy | 51.7% | 66.7% | +15.0% |
| Danger recall | 100.0% | 100.0% | +0.0% |
| Hard accuracy | 53.6% | 71.4% | +17.9% |
| Invalid/fallback | 0.0% | 0.0% | — |

## Theo lớp (improved)

| Nhãn | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| an_toan | 90.0% | 60.0% | 72.0% | 15 |
| nghi_ngo | 100.0% | 6.7% | 12.5% | 15 |
| nguy_hiem | 50.0% | 100.0% | 66.7% | 15 |
| khong_lien_quan | 79.0% | 100.0% | 88.2% | 15 |

## Failure modes

- Over-escalation: 13/15 tin nghi_ngo bị đẩy thành nguy_hiem; model còn quá bảo thủ với quà, đầu tư và giả danh mơ hồ.
- Scope ambiguity: các thông báo lịch hẹn/gia đình an toàn như safe-02, safe-07, safe-08 vẫn bị gán khong_lien_quan.
- Negation/money context: safe-05 và safe-09 bị gán nguy_hiem dù chỉ báo tiền vào hoặc cảnh báo không chia sẻ OTP.
