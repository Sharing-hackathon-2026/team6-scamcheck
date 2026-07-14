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

Kiểm tra tin nhắn nghi ngờ lừa đảo. Gemini được yêu cầu trả JSON mode; backend
sau đó chuẩn hoá bằng parser chịu lỗi trước khi trả cho trình duyệt.

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
  "usage": { "calls_used": 1, "call_limit": 10 }
}
```

- `excerpt` chỉ được giữ nếu xuất hiện nguyên văn trong `text`; parser xoá trích dẫn AI bịa.
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
