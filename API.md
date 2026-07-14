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

Kiểm tra tin nhắn nghi ngờ lừa đảo.

**Request**
```json
{ "text": "<nội dung tin nhắn>" }
```

**Response 200** (Cấp 1 — văn bản thô)
```json
{ "result": "Đây là tin nhắn lừa đảo vì..." }
```

**Response 400** — đầu vào không hợp lệ (rỗng / quá dài):
```json
{ "errors": ["Vui lòng dán nội dung tin nhắn cần kiểm tra."] }
```

**Response 502** — lỗi gọi AI:
```json
{ "error": "Không kết nối được tới AI. Vui lòng thử lại sau." }
```

> **Lưu ý Stage 2+:** response 200 sẽ đổi sang cấu trúc Thám tử:
> `{ "detective": { "risk_level": "...", "red_flags": [...], "actions": [...] } }`.
> Frontend cập nhật render tương ứng.
