# Hợp đồng API ScamCheck

Backend là REST API JSON dưới `/api/*`. Production dùng cùng origin qua Nginx.
Mọi text người dùng được chuẩn hóa Unicode NFC. Không endpoint nào trả quota phiên.

## `GET /api/health`

```json
{"ok": true, "ready": true}
```

`ready=false` khi thiếu `GEMINI_API_KEY`.

## `POST /api/check`

### Request

```json
{"text":"Nội dung tin nhắn cần kiểm tra"}
```

`text` phải là chuỗi không rỗng, tối đa 5000 ký tự.

### Response 200

```json
{
  "detective": {
    "risk_level": "an_toan | nghi_ngo | nguy_hiem | khong_lien_quan",
    "reason": "Giải thích ngắn",
    "red_flags": [
      {"label":"Yêu cầu OTP","excerpt":"gửi mã OTP","explanation":"..."}
    ],
    "actions": ["...", "...", "..."]
  },
  "psychologist": {"message":"Cô hiểu vì sao lời này dễ làm bác lo..."},
  "psychologist_status": "complete | not_needed | unavailable",
  "psychologist_error": null,
  "technical_analysis": {
    "links": [
      {
        "source_url": "bit.ly/vi-du",
        "normalized_url": "https://bit.ly/vi-du",
        "original_domain": "bit.ly",
        "final_url": "https://example.com/landing",
        "final_domain": "example.com",
        "resolved": true,
        "warnings": [
          {"code":"shortener","reason":"Đường dẫn rút gọn đang che tên miền đích.","official_domain":"","severity":"warning"}
        ]
      }
    ],
    "rule_signals": [
      {
        "code":"credential_request",
        "severity":"danger",
        "label":"Yêu cầu mã bí mật",
        "excerpt":"gửi mã OTP",
        "explanation":"..."
      }
    ]
  },
  "cache": {"hit": false, "ttl_seconds": 3600}
}
```

Quy tắc contract:

- Function name từ Gemini chỉ là advisory. Verdict sau parser + rule engine mới quyết định chain.
- Rule `danger` có thể nâng verdict thành `nguy_hiem`; rule `warning` chỉ nâng nhãn lạc quan lên `nghi_ngo`. Rule không hạ verdict AI.
- `excerpt` chỉ được giữ khi là lát cắt thật trong input.
- Relevant result luôn có đúng ba hành động; `khong_lien_quan` có danh sách rỗng.
- Cô tâm lý chỉ chạy cho `nghi_ngo`/`nguy_hiem`. Lỗi bước này vẫn trả HTTP 200 và giữ kết quả Thám tử.
- URL thường chỉ được phân tích tại chỗ. Shortener allowlisted mới được resolve với timeout, giới hạn redirect và chặn private/loopback/link-local/reserved IP mỗi hop.
- Cache key là SHA-256 của NFC input + model + pipeline version. Cache bounded/TTL, không persist plaintext; lỗi AI và `psychologist_status=unavailable` không được cache.
- `cache.hit=true` nghĩa là request trùng không gọi AI lại.

### Response 400

```json
{"errors":["Vui lòng dán nội dung tin nhắn cần kiểm tra."]}
```

### Response 502

```json
{"error":"AI đang quá tải hoặc tạm giới hạn lượt gọi. Vui lòng chờ ít phút rồi thử lại."}
```

## `GET /api/check/log`

Tối đa 10 metadata persona invocation gần nhất trong Flask session. Không lưu toàn văn tin.
Cache hit không tạo invocation giả.

```json
{
  "logs": [
    {
      "at":"2026-07-14T10:00:00+00:00",
      "actor":"detective | psychologist",
      "status":"complete | error | invalid_response",
      "input_length":86,
      "summary":"Mức rủi ro: nghi ngo"
    }
  ]
}
```

## `GET /api/scam-library`

Trả thư viện tĩnh ít nhất 12 kiểu thuộc bốn nhóm giả ngân hàng, giả công an,
trúng thưởng và giao hàng. Không gọi AI.

## `GET /api/quiz`

Trả đúng 10 câu luyện tập curated, không gọi AI:

```json
{
  "questions": [
    {
      "id":"q01",
      "text":"...",
      "is_scam":true,
      "category":"Giả ngân hàng",
      "explanation":"...",
      "tip":"..."
    }
  ]
}
```
