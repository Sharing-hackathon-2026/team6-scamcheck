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
- Cache key là SHA-256 của NFC input + model + pipeline version. Value typed được persist trong SQLite với TTL/capacity dùng chung giữa gunicorn worker; lỗi AI và `psychologist_status=unavailable` không được cache.
- `cache.hit=true` nghĩa là request trùng không gọi AI lại.

### Response 400

```json
{"errors":["Vui lòng dán nội dung tin nhắn cần kiểm tra."]}
```

### Response 502

```json
{"error":"AI đang quá tải hoặc tạm giới hạn lượt gọi. Vui lòng chờ ít phút rồi thử lại."}
```

## Thuộc tính `orchestration` trong `/api/check`

Stage 5 bổ sung máy trạng thái theo verdict đã qua parser/guardrail. Đây là trường additive,
không làm thay đổi contract Stage 1–4:

```json
{
  "orchestration": {
    "state": "awaiting_situation | assessment_complete",
    "personas_completed": ["detective", "psychologist"],
    "next_event": "situation_selected",
    "metrics": {"actual_ai_calls":2,"naive_ai_calls":3,"calls_saved":1}
  }
}
```

Cache hit có `actual_ai_calls=0`. Tool name từ Gemini không được quyền chuyển state.

## `POST /api/rescue`

### Request

```json
{
  "situation":"chua_lam_gi | da_bam_link | da_chuyen_tien | da_cung_cap_otp",
  "message_text":"Tin hiện tại, chỉ dùng local để dò tên ngân hàng",
  "risk_level":"nguy_hiem",
  "red_flags":[{"label":"Yêu cầu OTP"}]
}
```

Chỉ `situation` là bắt buộc. `message_text` tối đa 5000 ký tự và **không được truyền
nguyên văn vào prompt Người ứng cứu**; backend chỉ dùng để match alias ngân hàng.
`red_flags` được nhận để tương thích frontend nhưng bị bỏ tại trust boundary, không gửi AI.

### Response 200

```json
{
  "situation":"da_cung_cap_otp",
  "situation_label":"Đã cung cấp OTP, PIN hoặc mật khẩu",
  "praise":null,
  "rescue":{
    "situation":"da_cung_cap_otp",
    "headline":"Khóa quyền truy cập ngân hàng ngay",
    "reassurance":"...",
    "steps":[
      {
        "step":1,
        "key":"lock_bank_access",
        "action":"Gọi ngay Vietcombank",
        "detail":"...",
        "hotlines":[{
          "id":"vietcombank",
          "name":"Vietcombank",
          "phone":"1900 54 54 13",
          "type":"bank",
          "channel":"phone",
          "source_url":"https://www.vietcombank.com.vn/",
          "source_label":"Website chính thức Vietcombank",
          "reviewed_at":"2026-07-14",
          "emergency_only":false
        }]
      }
    ],
    "closing":"...",
    "is_fallback":false
  },
  "rescue_status":"complete | guarded_fallback | not_needed",
  "rescue_error":null,
  "matched_institutions":["Vietcombank"],
  "orchestration":{
    "state":"rescue_complete",
    "personas_completed":["rescuer"],
    "next_event":null,
    "metrics":{"actual_ai_calls":1,"naive_ai_calls":1,"calls_saved":0}
  },
  "call_savings_baseline":{
    "flows":4,"naive_rescuer_calls":4,"fsm_rescuer_calls":3,
    "calls_saved":1,"reduction_percent":25.0
  },
  "safety_notice":"..."
}
```

Quy tắc an toàn:

- `chua_lam_gi` không gọi AI, trả praise + playbook phòng ngừa (`not_needed`).
- Ba tình huống đã sa bẫy gọi Người ứng cứu tối đa một lần.
- AI lỗi hoặc thiếu safety step vẫn trả HTTP 200 với playbook deterministic và
  `rescue_status=guarded_fallback`; crisis flow không trở thành dead end.
- Mọi số giống điện thoại do model sinh đều bị post-filter. Chỉ số trong
  `backend/data/hotlines.json` và phù hợp tình huống mới được render lại từ bảng tĩnh.
- `113` có `emergency_only=true`, chỉ dành cho nguy hiểm/cần trợ giúp khẩn cấp.

### Response 400 / 503

- `400`: tình huống ngoài enum, JSON sai hoặc `message_text` quá dài.
- `503`: bảng hotline tĩnh không đọc/validate được; backend fail closed và không gọi AI.

## `GET /api/hotlines`

Trả bảng 10 ngân hàng + Công an + hệ thống phản ánh 156, gồm URL bằng chứng theo từng số,
trích dẫn, ngày kiểm tra, `channel=phone|sms` và lưu ý đối chiếu số in sau thẻ. Không gọi AI.

## `GET /api/share/qr.svg`

Trả QR Code Version 3-L chuẩn `image/svg+xml` dẫn về `BASE_URL`/same-origin ScamCheck.
Endpoint bỏ qua mọi query URL tùy ý và chỉ nhận `BASE_URL`/request host thuộc
`SHARE_ALLOWED_HOSTS`; production bắt buộc HTTPS. Host header/config ngoài allowlist trả 503,
không thể biến endpoint thành QR phishing. Không gọi dịch vụ QR ngoài và cache public một giờ.

## `GET /api/check/log` (compatibility)

Trả metadata invocation thuộc browser session hiện tại từ SQLite. Không lưu toàn văn tin/prompt;
cache hit không tạo invocation giả.

## `GET /api/ai-logs?scope=self|all`

- `scope=self` (mặc định): không cần đăng nhập, session id ngẫu nhiên nằm trong Flask cookie đã ký;
  response không lộ session id.
- `scope=all`: chỉ hoạt động qua origin exe.dev `:8001`, cần cả `X-ExeDev-UserID` và
  `X-ExeDev-Email` do Login with exe thêm; email phải có trong `ADMIN_ALLOWED_EMAILS`. Sai port/email trả `403`, chưa login trả `401`.
- Mọi response có `Cache-Control: no-store`.

```json
{
  "scope":"self",
  "admin_email":null,
  "stats":{
    "ai_calls":3,
    "checks":2,
    "risk_counts":{"an_toan":1,"nghi_ngo":0,"nguy_hiem":1,"khong_lien_quan":0},
    "actor_counts":{"detective":2,"psychologist":1},
    "retention_days":30
  },
  "logs":[{
    "id":1,
    "at":"2026-07-14T10:00:00+00:00",
    "actor":"detective",
    "status":"complete",
    "risk_level":"nghi_ngo",
    "input_length":86,
    "summary":"Mức rủi ro: nghi ngo"
  }]
}
```

## `GET /api/ai-logs/export?format=json|csv`

Xuất toàn bộ metadata còn trong retention window. Luôn yêu cầu exe.dev auth tại `:8001` và
email allowlist; CSV chặn formula injection. File không chứa nguyên văn tin nhắn hay prompt.

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
