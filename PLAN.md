:# ScamCheck — Kế hoạch triển khai (PLAN)

> Công cụ web giúp người từ 45 tuổi trở lên kiểm tra nhanh tin nhắn nghi ngờ lừa đảo
> (SMS, Zalo, Messenger, email), biết mức rủi ro, dấu hiệu lừa đảo cụ thể và cách xử lý.
> Công nghệ: **Python Flask REST + HTML/CSS token hoá + JavaScript thuần**. AI: **Google Gemini** qua HTTP.
>
> Nguồn: Đề bài Hackathon FCT: ScamCheck (`.docx`) và Backlog (`.xlsx`).

---

## 0. Nguyên tắc xuyên suốt

1. **Mỗi cấp là một sản phẩm chạy được hoàn chỉnh.** Mở ứng dụng ở bất kỳ cấp nào cũng dùng được.
2. **Luồng dữ liệu minh bạch:** không dùng framework ẩn — Flask route → service → Gemini HTTP → parse JSON → frontend render DOM. Hiểu rõ *tại sao chạy được*.
3. **Dòng lưu ý pháp lý hiện ở MỌI màn hình** (footer cố định):
   > *“ScamCheck là công cụ giáo dục do nhóm học viên phát triển và không thay thế cảnh báo chính thức từ ngân hàng hoặc cơ quan chức năng. Khi nghi ngờ, hãy gọi tổng đài chính thức in trên thẻ.”*
4. **Test cho mọi hàm** (pytest, theo quy định dự án) — đặc biệt hàm parse kết quả AI và các nhánh xử lý lỗi.
5. **Khóa bí mật ở env/`.env`, KHÔNG bao giờ commit.** Có `.env.example`.
6. **Thiết kế cho người 45+**: cỡ chữ ≥18px, độ tương phản AA, nút to, ít bước, không hù doạ, không làm xấu hổ người dùng.

---

## 1. Bản đồ cấp ↔ giai đoạn

> Theo backlog **nâng cấp** (bản 14/07, 50 hạng mục, ~125 giờ).

| Giai đoạn | Cấp | Nhóm tính năng | Số hạng mục | Mục tiêu | Skill liên quan |
|---|---|---|---|---|---|
| Stage 1 | Cấp 1: Nền tảng & vận hành | N1 | 8 | Kết quả có cấu trúc + parser chịu lỗi + retry rate-limit + trần tài nguyên + nhật ký gọi AI + lên mạng | — |
| Stage 2 | Cấp 2: Thám tử & Trải nghiệm | N2 + N3 | 10 | Thám tử schema, thẻ rủi ro, tô vàng, tin mẫu, 12 ca biên, AA iPhone, giọng nói, lịch sử | **anti-ai-design** (foundation), **utility-ui-eval** (gate) |
| Stage 3 | Cấp 3: Cô tâm lý & Thư viện | N4 | 6 | Chuỗi tuần tự, lỗi độc lập, chống prompt injection, bộ test hồi quy 20 tin, thư viện lừa đảo | anti-ai-design, utility-ui-eval (gate) |
| Stage 4 | Cấp 4: Chiều sâu kỹ thuật | N5 | 9 | Soi/giải link, tên miền giả (homoglyph), luật dấu hiệu, bộ 60 tin, đo chất lượng + ma trận nhầm lẫn, luyện tập, cache, streaming | anti-ai-design, utility-ui-eval (gate) |
| Stage 5 | Cấp 5: Người ứng cứu & chia sẻ | N6 | 10 | Bảng tổng đài, 4 tình huống, máy trạng thái 3 nhân vật, chặn số bịa, thẻ QR, tương phản cao | anti-ai-design, utility-ui-eval (gate cuối) |
| Stage 6 | N7: Sẵn sàng trình diễn | N7 | 7 | README, sơ đồ kiến trúc + FSM, slide, kịch bản demo, minh chứng AI, video, nhật ký kỹ thuật/phân định phần AI | — |

> Luồng Stage 6 chạy **song song** từ Stage 2.
> **Cấp 4** không còn "chọn cặp" — làm **đủ 9 hạng mục** (8 bắt buộc + 1 nên có).

---

## 2. Quy ước kỹ thuật

Dự án tách làm **hai phần độc lập**, cùng trong 1 repo (monorepo) để dễ bảo trì:

- **Frontend** (`frontend/`): HTML thuần + **CSS token hoá** + **JavaScript thuần**. Giao tiếp với backend qua `fetch`. Triển khai bằng **Nginx** (phục vụ file tĩnh). Không framework SPA.
- **Backend** (`backend/`): **Python Flask** — **REST API trả JSON thuần** (không Jinja2, không render HTML). `requests` gọi Gemini REST (`generativelanguage.googleapis.com`).

Chi tiết:
- **API contract:** mọi endpoint dưới tiền tố `/api/*`, trả `application/json`. Frontend gọi URL tương đối `fetch('/api/check')` → do Nginx reverse-proxy `/api/*` sang Flask, nên trình duyệt chỉ thấy **một origin** (không lo CORS).
- **Không session/đăng nhập** (ngoài phạm vi). Lịch sử lưu **localStorage phía trình duyệt** (JSON) theo đúng backlog (L2-09).
- **Model Gemini:** `gemini-2.x` qua endpoint `generateContent`, yêu cầu **JSON có cấu trúc** (`response_mime_type=application/json`) để parse deterministic.
- **Biến môi trường (backend):** `GEMINI_API_KEY` (mentor cấp), `GEMINI_MODEL`, `FLASK_SECRET_KEY`, `CORS_ORIGIN` (tuỳ chọn).
- **Cấu hình frontend:** `assets/js/config.js` (hoặc `config.example.js` + `.env` build) chỉ chứa `API_BASE` (thường để rỗng = cùng origin).
- **Test:** `pytest` trong `backend/tests/`. Coverage ≥ cho mọi hàm trong `backend/app/services/`.
- **Triển khai:** public SSL `https://team6-scamcheck.exe.xyz/`; edge forward tới Nginx port nội bộ `8000` trên VM target.
  - **Nginx** phục vụ `frontend/` tại `/` VÀ reverse-proxy `/api/*` → Flask.
  - **Flask (gunicorn)** chạy port nội bộ (vd `:5000`) qua systemd.
  - Hai service độc lập → sửa frontend không cần restart backend và ngược lại.
  - VM target **khác** VM dev hiện tại *(đề bài cho Render/Railway/GitHub Pages; ở đây dùng VM riêng + proxy công khai — tương đương "địa chỉ web công khai" ở Cấp 1 L1-05).*

---

## 3. Chi tiết từng Stage

### Stage 0 — Khởi tạo (đã xong)

- [x] Repo `Sharing-hackathon-2026/team6-scamcheck` (remote có sẵn).
- [x] `.gitignore` (loại trừ `.env`, `__pycache__`, `venv`, `*.db`).
- [x] `.env.example` (không chứa key thật) + hướng dẫn điền key.
- [x] Cấu trúc monorepo (frontend/ + backend/) + Flask skeleton.
- [x] `backend/requirements.txt`, `backend/pytest.ini` (34 test xanh).
- [x] `requests` + verify key thật `gemini-3.1-flash-lite` gọi OK.
- [x] Harden Stage 1 system prompt (từ chối tin không liên quan → tiết kiệm quota; tiền đề cho L1-07/L1-08).

> **Lưu ý quan trọng — backlog NÂNG CẤP (bản 14/07):** Backlog mới làm **thay đổi định nghĩa Cấp 1** — L1-03 mới yêu cầu kết quả **có cấu trúc** ngay từ Cấp 1 (không còn "bản thô text"), thêm L1-04 (parser chịu lỗi), L1-05 (retry rate-limit), L1-07 (trần tài nguyên), L1-08 (nhật ký gọi AI). Cấp 4 không còn "chọn cặp B+C" mà là 9 hạng mục nặng đo lường. Cấp 3 thêm chống prompt injection + thư viện lừa đảo. Cấp 5 thêm máy trạng thái + thẻ QR. N7 thêm nhật ký kỹ thuật/phân định phần AI. Bảng dưới đánh giá trạng thái codebase hiện tại theo từng mã backlog mới.

---

### Stage 1 — Cấp 1: Nền tảng và vận hành (N1) — 8 hạng mục

> **Định nghĩa mới:** Cấp 1 đã yêu cầu **kết quả có cấu trúc cố định** (mức rủi ro + dấu hiệu kèm đoạn trích + hành động), parser chịu lỗi, retry khi rate-limit, trần tài nguyên và nhật ký gọi AI.

| Mã | Hạng mục | Ưu tiên | Trạng thái | Ghi chú đánh giá |
|---|---|---|---|---|
| L1-01 | Khởi tạo kho mã và bảo mật khoá | Bắt buộc | ✅ Xong | `.gitignore` + `.env.example`; scan git history = 0 key |
| L1-02 | Giao diện nhập liệu và dòng pháp lý | Bắt buộc | ✅ Xong | `frontend/index.html`: textarea lớn + nút Kiểm tra + footer pháp lý cố định |
| L1-03 | Gọi Gemini trả **kết quả có cấu trúc** | Bắt buộc | ✅ Xong | `/api/check` trả `detective` có risk level, dấu hiệu/đoạn trích và đúng 3 hành động |
| L1-04 | Hàm đọc kết quả chịu lỗi | Bắt buộc | ✅ Xong | `parse_detective()` validate/coerce; JSON sai → fallback `nghi_ngo`; xoá excerpt AI bịa; 6 test |
| L1-05 | Xử lý ca biên + **thử lại khi rate-limit** | Bắt buộc | ✅ Xong | Validate rỗng/>5000; retry 429/503 tối đa 2 lần (0.5s, 1s); exhausted/mạng → lỗi thân thiện 502 |
| L1-06 | Triển khai lên mạng công khai | Bắt buộc | ✅ Xong | Live tại https://team6-scamcheck.exe.xyz/ (full SSL edge → nginx + gunicorn, verified end-to-end) |
| L1-07 | Trần tài nguyên gọi AI | Bắt buộc | ✅ Xong | Theo yêu cầu sản phẩm mới: bỏ quota phiên; vẫn giữ timeout ≤8s, retry hữu hạn và log metadata 10 mục |
| L1-08 | Nhật ký gọi AI | Nên có | ✅ Xong | `GET /api/check/log`; tối đa 10 metadata/lượt trong session (thời điểm, độ dài, tóm tắt), không lưu nội dung tin |

**Test (pytest):** 41 test xanh: JSON mode, parser fallback/excerpt, retry 429/503, session log, validation, prompt và routes.

**Tiêu chí hoàn thành Cấp 1 (mới):** 9/10 lần AI trả đúng cấu trúc; ≤30s; 5 ca biên không gãy; retry 429 đúng cơ chế; timeout hữu hạn + nhật ký.

---

### Stage 2 — Cấp 2: N2 Thám tử + N3 Trải nghiệm — 10 hạng mục

> 🎨 **Gate anti-ai-design (đầu Stage 2):** chốt mobile (iPhone Safari chuẩn) + responsive desktop; palette tin cậy + 3 màu ngữ nghĩa (An toàn=Xanh / Nghi ngờ=Vàng / Nguy hiểm=Đỏ) AA; style thân thiện 45+ (chữ ≥18px, nút to). Đóng băng `frontend/assets/css/tokens.css`.

| Mã | Hạng mục | Ưu tiên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| L2-01 | Hồ sơ & câu lệnh Thám tử | Bắt buộc | ✅ Xong | Giọng khô khan, lý tính; input là dữ liệu không tin cậy; schema cố định + guardrail không hạ tín hiệu nguy hiểm thành An toàn |
| L2-02 | Thẻ màu mức rủi ro | Bắt buộc | ✅ Xong | Thẻ Xanh/Vàng/Đỏ có nhãn chữ, biểu tượng, viền; hỗ trợ Không liên quan |
| L2-03 | Dấu hiệu + tô vàng đoạn trích | Bắt buộc | ✅ Xong | `highlight-excerpts.js` khớp hoa/thường + khoảng trắng, hợp nhất overlap, render text node chống XSS; không thấy thì bỏ qua |
| L2-04 | Danh sách hành động khuyến nghị | Bắt buộc | ✅ Xong | Backend + frontend chuẩn hoá đúng 3 hành động, cỡ chữ ≥18px |
| L2-05 | Lịch sử 10 tin gần nhất (localStorage) | Bắt buộc | ✅ Xong | Tối đa 10, khử trùng, xem lại từ localStorage không gọi AI |
| L2-06 | Nút tin mẫu + màn hình chờ | Nên có | ✅ Xong | 3 tin mẫu; loading có status, spinner, skeleton và reduced-motion |
| L2-07 | Mở rộng lên 12 ca biên | Bắt buộc | ✅ Xong | 12 ca gán nhãn chạy ở service + route, gồm link giả và tiêu đề/thân mâu thuẫn; không gọi Gemini thật |
| L2-08 | Chuẩn tiếp cận AA trên iPhone | Bắt buộc | ✅ Xong | Chữ ≥18px, touch ≥44px, focus-visible, aria-live, reflow 320px; bảng tự kiểm `frontend/ACCESSIBILITY.md` |
| L2-09 | Nhập tin bằng giọng nói | Bắt buộc | ✅ Xong | Web Speech API + `webkitSpeechRecognition`, bật/tắt, lỗi quyền/micro/mạng thân thiện, fallback khi không hỗ trợ |
| L2-10 | Quản lý & xoá lịch sử | Nên có | ✅ Xong | Xoá từng mục/toàn bộ, có xác nhận và accessible name |

**Test Stage 2:** `77` pytest backend + `21` Node tests frontend; compileall, node syntax, `git diff --check` đều đạt. Smoke test Gemini thật xác nhận model `gemini-3.1-flash-lite` chấp nhận schema tương thích và trả đúng contract.

**🚦 Gate utility-ui-eval (cuối Stage 2):** ✅ PASS — evaluator độc lập `step-3.7-flash` (ZenMux) chấm `8.0/10`, `true_operational_tool`, `usable=true`, không có critical/major finding, khuyến nghị `ship`. Minor: shortcut chưa có gợi ý trực quan, nút xoá lịch sử dùng icon-only (đã có accessible name), và điều hướng lịch sử còn tối giản.

---

### Stage 3 — Cấp 3: N4 Cô tâm lý + Thư viện — 6 hạng mục

### Stage 3 implementation architecture (chốt trước khi code)

- Thám tử dùng **forced terminal function call** thay cho JSON text: chọn
  `complete_detective` hoặc `handoff_to_psychologist`, với arguments chứa trọn
  DetectiveResult. Backend coi tool choice và arguments là dữ liệu không tin cậy,
  chạy parser/guardrail rồi mới quyết định kích hoạt bước hai.
- Tool là handoff một chiều: backend không gửi `functionResponse` về Thám tử và
  không gọi lượt tổng hợp cuối. Tin an toàn dùng 1 lượt AI; tin nghi ngờ/nguy hiểm
  dùng tối đa 2 lượt AI.
- Cô tâm lý phụ thuộc verdict đã parse nên critical path vẫn tuần tự. Function calling
  làm orchestration rõ hơn nhưng không giả định hai model call chạy song song.
- Payload giữ `detective` tương thích Stage 2 và thêm `psychologist`,
  `psychologist_status`, `psychologist_error`; không trả usage/quota phiên.
- `psychologist_status` thuộc `complete | not_needed | unavailable`; lỗi bước hai
  không đổi HTTP 200 hay che kết quả Thám tử.
- Không giới hạn lượt theo phiên. Audit chỉ lưu actor, trạng thái,
  độ dài input và tóm tắt; không lưu nội dung tin.
- Route dùng budget hữu hạn: Thám tử timeout 6s + tối đa một retry rate-limit;
  Cô tâm lý timeout 5s, không retry, giữ worst-case AI wait dưới 20s.
- Psychologist schema chỉ có `message`; parser ép 2–3 câu và thay fallback khi model
  đổi vai, tiết lộ prompt hoặc hạ verdict thành “an toàn/không lừa đảo”.
- `GET /api/scam-library` đọc JSON tĩnh 12 mẫu/4 nhóm. Frontend filter/hash navigation
  hoàn toàn client-side, không reload và có loading/empty/error/success state.
- `backend/scripts/run_regression.py` chạy 20 tin gán nhãn với Gemini thật khi gọi chủ
  động; CI kiểm tra dataset/report bằng predictor giả nên không tiêu quota.


| Mã | Hạng mục | Ưu tiên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| L3-01 | Hồ sơ & câu lệnh Cô tâm lý | Bắt buộc | ✅ Xong | Giọng cô–bác, 2–3 câu, JSON schema riêng; parser chặn đổi vai/hạ verdict |
| L3-02 | Chuỗi tuần tự + hiển thị 2 phần | Bắt buộc | ✅ Xong | Terminal function-call handoff; không lượt tổng hợp cuối; UI tách thẻ Thám tử/Cô tâm lý |
| L3-03 | Điều kiện kích hoạt + lỗi độc lập | Bắt buộc | ✅ Xong | Verdict sau guardrail quyết định; lỗi Cô tâm lý vẫn trả HTTP 200 và giữ Thám tử |
| L3-04 | **Chống chèn lời nhắc (prompt injection)** | Bắt buộc | ✅ Xong | Hai prompt coi input là dữ liệu không tin cậy; tool name advisory; parser hậu kiểm cả hai persona |
| L3-05 | Bộ kiểm thử hồi quy 20 tin | Bắt buộc | ✅ Xong | 20 tin/4 nhãn, loader/evaluator/report test không gọi AI; script CLI chạy Gemini thật |
| L3-06 | Thư viện kiểu lừa đảo | Bắt buộc | ✅ Xong | 12 kiểu, 4 nhóm, API tĩnh; filter/hash navigation client-side không reload |

**🚦 Gate utility-ui-eval Stage 3:** ✅ PASS — evaluator độc lập Grok 4.5 chấm
`8.2/10`, `true_operational_tool`, `usable=true`, không có critical finding và
khuyến nghị `ship`. Sau gate đã đưa lịch sử lên trước thư viện ở mobile; voice
fallback và accessible names tiếp tục được phủ bởi test Stage 2.


---

### Stage 4 — Cấp 4: N5 Chiều sâu kỹ thuật — 9 hạng mục

> **Thay đổi lớn so với backlog cũ:** không còn "chọn cặp B+C" — 9 hạng mục cụ thể, nặng về đo lường chất lượng AI có số liệu.
>
> **Kiến trúc triển khai đã chốt trước khi code:** URL thường chỉ phân tích tại chỗ;
> shortener mới được resolve với chặn SSRF mỗi hop. Rule engine pure-function merge sau
> parser theo chính sách chỉ nâng rủi ro. Cache TTL/LRU dùng hash NFC + model + pipeline
> version, không persist plaintext. Bộ 60 tin có dev/eval split; runner throttle hỗ trợ
> baseline Stage 3 và improved Stage 4, đồng thời có thể chấm cùng raw output để cô lập
> tác động rule. Function-call typed được giữ nguyên;
> phản hồi thời gian thực ưu tiên progress state + cancel thay vì token stream không ổn định.

| Mã | Hạng mục | Ưu tiên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| L4-01 | Soi và **giải** đường dẫn | Bắt buộc | ✅ Xong | Tách scheme/www/bare URL; shortener resolve ≤3 hop, timeout, không đọc body, chặn SSRF mỗi hop |
| L4-02 | Phát hiện tên miền giả bằng thuật toán | Bắt buộc | ✅ Xong | IDN/punycode, zero-width, mixed-script, confusable skeleton, Levenshtein; test 11 kiểu giả |
| L4-03 | Phát hiện dấu hiệu bằng **luật** | Bắt buộc | ✅ Xong | Pure rules OTP/dữ liệu/tiền/STK/khẩn cấp/URL; phủ định theo mệnh đề; merge chỉ nâng verdict |
| L4-04 | Bộ dữ liệu đánh giá **60 tin** | Bắt buộc | ✅ Xong | 60 tin cân bằng 15/nhãn, 28 ca khó, dev/eval split, rationale/tags, dữ liệu tổng hợp NFC |
| L4-05 | Đo chất lượng AI có số liệu | Bắt buộc | ✅ Xong | JSON+Markdown: accuracy, class metrics, confusion, latency, invalid, 3 failure modes và metadata tái lập |
| L4-06 | Cải thiện dựa trên số liệu | Bắt buộc | ✅ Xong | Prompt scope + rules: accuracy 51,7%→66,7%; hard accuracy 53,6%→71,4%; danger recall giữ 100% |
| L4-07 | Chế độ luyện tập 10 câu | Bắt buộc | ✅ Xong | `/practice.html`: chấm ngay, giải thích/mẹo, tổng kết, restart, native keyboard/screen-reader controls |
| L4-08 | Phản hồi thời gian thực (streaming) | Nên có | ✅ Xong | Progressive stage text xuất hiện ngay và đổi trong <3s; AbortController hủy request; giữ typed function-call parsing |
| L4-09 | Bộ nhớ đệm kết quả | Bắt buộc | ✅ Xong | SHA-256 NFC+model+version, TTL/LRU 256 mục/1h mỗi process; cache hit không gọi AI; không cache lỗi |

**Test:** 150 pytest backend + 29 Node tests frontend; gồm `test_links.py`, `test_homoglyph.py`, `test_rule_engine.py`, `test_cache.py`, `test_quiz.py`, `test_eval_report.py`.

**🚦 Gate utility-ui-eval Stage 4:** ✅ PASS — evaluator vision độc lập
`gemini-3.1-flash-lite` chấm `9,5/10`, `usable=true`, không có critical/major finding.
Đã xem desktop/mobile empty, result + technical evidence, quiz feedback và input-error attempt.
Minor duy nhất nhắc kiểm tra touch target nút mẫu; CSS toàn cục đang cưỡng chế `min-height:44px`.
Evidence machine-readable: `backend/reports/stage4-ux-gate.json`.

**🎨 Post-Stage-4 visual refinement:** Pi builder `glm-5.2` áp dụng anti-ai-design,
community-notice palette và auto light/dark theo system. Fresh evaluator `gpt-5.6-terra`
chạy rubric 28 chiều + Browse CLI; sau khi sửa mobile density và quiz retry:
main `8,6/10`, practice `8,0/10`, cả hai `true_operational_tool`, không critical/major,
`recommend=ship`. Evidence: `backend/reports/human-dark-ux-gate.json`.

---

### Stage 5 — Cấp 5: N6 Người ứng cứu + chia sẻ — 10 hạng mục

| Mã | Hạng mục | Ưu tiên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| L5-01 | Bảng tổng đài đã xác minh | Bắt buộc | ✅ Xong | 10 NH + 113 + 156; URL/evidence/date theo từng số; live verifier 12/12 exact match |
| L5-02 | Câu hỏi tình huống 4 lựa chọn | Bắt buộc | ✅ Xong | Bốn native button một chạm; lock sau thành công, error/retry thật |
| L5-03 | Hồ sơ & câu lệnh Người ứng cứu | Bắt buộc | ✅ Xong | Prompt runtime whitelist; copy hiển thị deterministic, bình tĩnh/dứt khoát; không render AI prose |
| L5-04 | Kịch bản 4 tình huống | Bắt buộc | ✅ Xong | 4 playbook riêng; đủ step keys; AI/network/off đều có guarded fallback |
| L5-05 | Điều phối 3 nhân vật bằng **máy trạng thái** | Bắt buộc | ✅ Xong | FSM verdict/situation; `chua_lam_gi` 0 Rescuer call; baseline giảm 25% |
| L5-06 | Chặn ảo giác số điện thoại | Bắt buộc | ✅ Xong | URL/email/số lạ fail closed; hotline ID allowlist từng step; 113 không auto-attach |
| L5-07 | Kiểm thử luồng khủng hoảng + tài liệu vận hành | Bắt buộc | ✅ Xong | 193 pytest; runbook + kill switch + safety report; fresh safety mentor PASS |
| L5-08 | Thẻ tóm tắt kết quả chia sẻ + mã QR | Bắt buộc | ✅ Xong | Canvas PNG 1080×1350, privacy redaction, QR Version 3-L same-origin allowlisted |
| L5-09 | Nút tải ảnh về máy | Nên có | ✅ Xong | Web Share File + Blob download; iOS fallback mở ảnh/chạm giữ; cần smoke iPhone thật |
| L5-10 | Tương phản cao + cỡ chữ điều chỉnh | Bắt buộc | ✅ Xong | High contrast light/dark + 100/115/130%, localStorage fail-safe dùng cả hai trang |

**Test hiện tại:** 202 pytest backend + 80 Node tests frontend; compileall/syntax/NFC/diff check đạt.

**🛡️ Safety mentor gate:** ✅ PASS — fresh `gpt-5.6-terra`, không critical/major,
`recommendation=ship`. Hai vòng FAIL trước đã buộc sửa AI prose, 113, Host-header QR và
nguồn hotline. Evidence: `backend/reports/stage5-safety-evaluation.json` +
`stage5-hotline-verification.json`.

**🚦 Gate utility-ui-eval Stage 5:** ✅ PASS — fresh vision `gpt-5.6-terra`, `7,7/10`,
`true_operational_tool`, usable, không critical/major, `recommend=ship`.
Evidence: `backend/reports/stage5-ux-gate.json`.

---

### Stage 6 — N7: Sẵn sàng trình diễn (song song từ Cấp 2) — 7 hạng mục

| Mã | Hạng mục | Ưu tiên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| N7-01 | Tệp giới thiệu dự án (README) | Bắt buộc | ⚠️ Có bản nháp | Cần cập nhật theo backlog mới (tính năng, cách chạy, nhóm) |
| N7-02 | Sơ đồ kiến trúc + sơ đồ trạng thái | Bắt buộc | ❌ | Cần thêm sơ đồ FSM 3 nhân vật (L5-05) |
| N7-03 | Slide 8–10 trang | Bắt buộc | ❌ | Có số liệu đo chất lượng (từ L4-05) + dòng pháp lý |
| N7-04 | Kịch bản demo 3–5 phút | Bắt buộc | ❌ | Luồng chính + ca biên + tình huống khủng hoảng |
| N7-05 | Minh chứng AI + báo cáo đo chất lượng | Nên có | ❌ | Screenshot prompt+response ≥3 tin + báo cáo L4-05 |
| N7-06 | Video dự phòng <5 phút | Nên có | ❌ | Offline-ready |
| N7-07 | **Nhật ký kỹ thuật + phân định phần AI** | Bắt buộc | ❌ | Ghi rõ phần nào AI sinh / nhóm tự chỉnh + lý do, quyết định khó, lỗi gặp. **Mới** |

---

---

## 4. Quyết định thiết kế (chốt Stage 0)

| Quyết định | Lựa chọn | Lý do |
|---|---|---|
| Kiến trúc | **Tách frontend/backend** (monorepo) | Bảo trì dễ: sửa UI không đụng API và ngược lại |
| Frontend | HTML + CSS token hoá + JS thuần → **Nginx** | Theo option 1 đề bài, hiểu rõ luồng fetch |
| Backend | **Flask REST API** (JSON, không Jinja2) | Phần API trong sáng, test độc lập |
| Giao tiếp FE→BE | `/api/*` qua reverse-proxy Nginx (cùng origin) | Không lo CORS, URL tương đối |
| Gọi Gemini | HTTP `requests` (không SDK) | Kiểm soát tuần tự, dễ mock/test, hiểu rõ luồng |
| Cấu trúc AI | `response_mime_type=application/json` + schema | Parse deterministic, đáp ứng "9/10 lần đúng cấu trúc" |
| Lịch sử | localStorage trình duyệt | Theo backlog L2-05, không cần backend state |
| Cấp 4 | Làm **đủ 9 hạng mục** (không chọn cặp) | Backlog nâng cấp yêu cầu đo lường chất lượng AI có số liệu (L4-04→L4-06) |
| Triển khai | Nginx (static) + gunicorn (Flask) trên VM target | Public SSL không port; edge forward tới Nginx `:8000` |

---

## 5. Thứ tự ưu tiên & phụ thuộc

```
Stage 0 ──▶ Stage 1 ──▶ Stage 2 ──▶ Stage 3 ──▶ Stage 4 ──▶ Stage 5
                              │
                              └──▶ Stage 6 (N7, song song từ đây)
```

- Stage 2 là **mốc bảo vệ tối thiểu** (sản phẩm thật). Nếu dừng ở đây vẫn có giá trị.
- **anti-ai-design** chạy ở đầu Stage 2 và mỗi khi thêm màn hình mới (3/4/5).
- **utility-ui-eval** là **gate chặn** ở cuối mỗi Stage 2–5: chưa PASS không sang stage sau.
- Test pytest chạy liên tục, mỗi PR phải xanh.

---

## 6. Rủi ro & giảm thiểu

| Rủi ro | Giảm thiểu |
|---|---|
| AI trả lệch cấu trúc | JSON mode + parser có fallback (L2-02) + 5 case test |
| Key lộ git | `.gitignore`, pre-commit scan, `.env.example` |
| Nguy hiểm thực tế ở Cấp 5 (số sai) | `hotlines.json` tĩnh + post-filter số, mentor duyệt |
| Chậm >20s (Cấp 3) | Giảm token, model nhanh, song song được thì song song (giữ thứ tự UI) |
| iPhone Safari vỡ layout | Gate utility-ui-eval chụp viewport iPhone |
