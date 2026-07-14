## `GET /api/scam-library`

Trả thư viện tĩnh ít nhất 12 kiểu lừa đảo thuộc đúng bốn nhóm: giả ngân hàng,
giả công an, trúng thưởng và giao hàng. Endpoint không gọi AI; frontend lọc theo
nhóm và URL hash mà không reload.

---

# Hợp đồng API ScamCheck

Backend là REST API thuần JSON, tiền tố `/api/*`. Frontend gọi qua cùng origin (Nginx proxy).

## `GET /api/health`

Health check (cho Nginx / giám sát).

**Response 200**
```json
{ "ok": true, "ready": true }
```
`ready=false` khi chưa cấu hình `GEMINI_API_KEY`.

---

## `POST /api/check`

Kiểm tra tin nhắn nghi ngờ lừa đảo. Thám tử kết thúc sớm bằng function call
`complete_detective` hoặc `handoff_to_psychologist`; backend luôn parse/guardrail
arguments trước khi quyết định có gọi Cô tâm lý hay không. Cô tâm lý dùng JSON mode.

**Request**
```json
{ "text": "<nội dung tin nhắn>" }
```

**Response 200**
```json
{
  "detective": {
    "risk_level": "an_toan | nghi_ngo | nguy_hiem | khong_lien_quan",
    "reason": "Giải thích ngắn, dễ hiểu",
    "red_flags": [
      { "label": "Yêu cầu OTP", "excerpt": "gửi mã OTP", "explanation": "..." }
    ],
    "actions": ["...", "...", "..."]
  },
  "psychologist": {
    "message": "Cô hiểu vì sao lời thúc giục này dễ làm bác lo..."
  },
  "psychologist_status": "complete | not_needed | unavailable | quota_reached",
  "psychologist_error": null,
  "usage": { "calls_used": 2, "call_limit": 10 }
}
```

- `psychologist` chỉ có khi verdict sau guardrail là `nghi_ngo`/`nguy_hiem` và lượt thứ hai thành công.
- Cô tâm lý lỗi/hết quota không che kết quả Thám tử; API vẫn trả 200 với trạng thái độc lập.
- Quota đếm từng lần gọi AI thực tế: tin an toàn thường tốn 1, tin cần Cô tâm lý tối đa 2.
- `excerpt` chỉ được giữ nếu xuất hiện nguyên văn trong `text`; parser xoá trích dẫn AI bịa.
- Gemini nhận `response_schema` theo tập con JSON Schema mà REST API hỗ trợ; hợp đồng nghiêm ngặt
  (không trường thừa) vẫn được nhúng trong system prompt và cưỡng chế lại bởi parser.
- Guardrail hậu kiểm nâng `an_toan`/`khong_lien_quan` thành `nguy_hiem` khi input có yêu cầu tiền,
  credential/thông tin nhạy cảm, URL đáng ngờ hoặc đe doạ khẩn cấp rõ ràng.
- Khi AI trả JSON lỗi, API vẫn trả 200 với fallback `risk_level="nghi_ngo"` và ba hành động an toàn.
- Mức `khong_lien_quan` có `red_flags` và `actions` rỗng.

**Response 400** — đầu vào không hợp lệ (rỗng / quá dài):
```json
{ "errors": ["Vui lòng dán nội dung tin nhắn cần kiểm tra."] }
```

**Response 429** — đã dùng hết quota của phiên trình duyệt:
```json
{ "error": "...", "code": "ai_call_limit_reached", "calls_used": 10, "call_limit": 10 }
```

**Response 502** — Gemini/mạng lỗi, kể cả sau retry 429/503:
```json
{ "error": "AI đang quá tải hoặc tạm giới hạn lượt gọi. Vui lòng chờ ít phút rồi thử lại." }
```

## `GET /api/check/log`

Nhật ký 10 lượt gọi gần nhất của **phiên hiện tại**. Chỉ lưu thời điểm, độ dài input,
tóm tắt mức rủi ro — không lưu hay trả lại toàn văn tin nhắn.

```json
{
  "logs": [{ "at": "2026-07-14T10:00:00+00:00", "input_length": 86, "summary": "Mức rủi ro: nghi ngo" }],
  "calls_used": 1,
  "call_limit": 10
}
```
