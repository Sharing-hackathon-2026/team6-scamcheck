:# ScamCheck — Kế hoạch triển khai (PLAN)

> Công cụ web giúp người từ 45 tuổi trở lên kiểm tra nhanh tin nhắn nghi ngờ lừa đảo
> (SMS, Zalo, Messenger, email), biết mức rủi ro, dấu hiệu lừa đảo cụ thể và cách xử lý.
> Công nghệ: **Python Flask + Jinja2 + Tailwind (CDN)**. AI: **Google Gemini** qua HTTP.
>
> Nguồn: Đề bài Hackathon FCT: ScamCheck (`.docx`) và Backlog (`.xlsx`).

---

## 0. Nguyên tắc xuyên suốt

1. **Mỗi cấp là một sản phẩm chạy được hoàn chỉnh.** Mở ứng dụng ở bất kỳ cấp nào cũng dùng được.
2. **Luồng dữ liệu minh bạch:** không dùng framework ẩn — Flask route → service → Gemini HTTP → parse → render Jinja2. Hiểu rõ *tại sao chạy được*.
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

- **Frontend** (`frontend/`): HTML thuần + **Tailwind CSS** (CDN hoặc build) + **JavaScript thuần**. Giao tiếp với backend qua `fetch`. Triển khai bằng **Nginx** (phục vụ file tĩnh). Không framework SPA.
- **Backend** (`backend/`): **Python Flask** — **REST API trả JSON thuần** (không Jinja2, không render HTML). `requests` gọi Gemini REST (`generativelanguage.googleapis.com`).

Chi tiết:
- **API contract:** mọi endpoint dưới tiền tố `/api/*`, trả `application/json`. Frontend gọi URL tương đối `fetch('/api/check')` → do Nginx reverse-proxy `/api/*` sang Flask, nên trình duyệt chỉ thấy **một origin** (không lo CORS).
- **Không session/đăng nhập** (ngoài phạm vi). Lịch sử lưu **localStorage phía trình duyệt** (JSON) theo đúng backlog (L2-09).
- **Model Gemini:** `gemini-2.x` qua endpoint `generateContent`, yêu cầu **JSON có cấu trúc** (`response_mime_type=application/json`) để parse deterministic.
- **Biến môi trường (backend):** `GEMINI_API_KEY` (mentor cấp), `GEMINI_MODEL`, `FLASK_SECRET_KEY`, `CORS_ORIGIN` (tuỳ chọn).
- **Cấu hình frontend:** `assets/js/config.js` (hoặc `config.example.js` + `.env` build) chỉ chứa `API_BASE` (thường để rỗng = cùng origin).
- **Test:** `pytest` trong `backend/tests/`. Coverage ≥ cho mọi hàm trong `backend/app/services/`.
- **Triển khai (VM target `team6-scamcheck.exe.xyz`, proxy công khai port `8000`):**
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
| L1-03 | Gọi Gemini trả **kết quả có cấu trúc** | Bắt buộc | ⚠️ CẦN NÂNG CẤP | Hiện route trả `{"result": <text thô>}`. Backlog mới yêu cầu cấu trúc {risk_level, red_flags[].excerpt, actions[]} + JSON mode. `generate_json()` đã có sẵn trong services/gemini.py nhưng chưa wire vào route. Cần thêm prompt Thám tử schema + parser |
| L1-04 | Hàm đọc kết quả chịu lỗi | Bắt buộc | ❌ Chưa có | Cần `app/services/parser.py:parse_detective()` validate schema + fallback mặc định an toàn, test 5 mẫu lệch cấu trúc |
| L1-05 | Xử lý ca biên + **thử lại khi rate-limit** | Bắt buộc | ⚠️ Một phần | Đã có validate rỗng/>5000 ký tự + bắt lỗi mạng/AI (502). **Chưa có:** retry khi 429/503 với backoff tăng dần tối đa 2 lần; mở rộng đủ 5 ca biên |
| L1-06 | Triển khai lên mạng công khai | Bắt buộc | ✅ Xong | Live tại https://team6-scamcheck.exe.xyz:8000/ (nginx + gunicorn, verified end-to-end) |
| L1-07 | Trần tài nguyên gọi AI | Bắt buộc | ❌ Chưa có | Cần giới hạn số lần gọi AI/phiên (vd 10) + timeout max/gọi; hiển thị số lần đã dùng; chạm trần → báo lịch sự. Harden refusal (đã làm) là tiền đề giảm tiêu hao |
| L1-08 | Nhật ký gọi AI | Nên có | ❌ Chưa có | Ghi {thời điểm, độ dài đầu vào, tóm tắt kết quả} mỗi lần gọi; xem lại trong phiên; phục vụ đo lường Cấp 4 |

**Test (pytest):** `test_gemini_client.py`, `test_routes.py`, `test_validation.py`, `test_prompts.py` (34 test xanh). **Cần thêm:** `test_parser_detective.py`, `test_retry_ratelimit.py`.

**Tiêu chí hoàn thành Cấp 1 (mới):** 9/10 lần AI trả đúng cấu trúc; ≤30s; 5 ca biên không gãy; retry 429 đúng cơ chế; có trần + nhật ký.

---

### Stage 2 — Cấp 2: N2 Thám tử + N3 Trải nghiệm — 10 hạng mục

> 🎨 **Gate anti-ai-design (đầu Stage 2):** chốt mobile (iPhone Safari chuẩn) + responsive desktop; palette tin cậy + 3 màu ngữ nghĩa (An toàn=Xanh / Nghi ngờ=Vàng / Nguy hiểm=Đỏ) AA; style thân thiện 45+ (chữ ≥18px, nút to). Đóng băng `frontend/assets/css/tokens.css`.

| Mã | Hạng mục | Ưu tiên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| L2-01 | Hồ sơ & câu lệnh Thám tử | Bắt buộc | ❌ | Giọng khô khan lý tính + giữ cấu trúc cố định. Đích: đúng ≥27/30 tin ẩn mentor, KHÔNG có tin Nguy hiểm nào bị gán An toàn |
| L2-02 | Thẻ màu mức rủi ro | Bắt buộc | ❌ | Xanh/Vàng/Đỏ ở đầu màn hình kết quả |
| L2-03 | Dấu hiệu + tô vàng đoạn trích | Bắt buộc | ❌ | JS `highlight-excerpts.js`: bọc `<mark>` đúng vị trí; không tìm thấy thì bỏ qua |
| L2-04 | Danh sách hành động khuyến nghị | Bắt buộc | ❌ | Đúng 3 hành động, cỡ chữ ≥18px |
| L2-05 | Lịch sử 10 tin gần nhất (localStorage) | Bắt buộc | ❌ | Xem lại không gọi AI; tối đa 10, đẩy cũ nhất ra |
| L2-06 | Nút tin mẫu + màn hình chờ | Nên có | ❌ | 3 nút điền sẵn; loading mượt |
| L2-07 | Mở rộng lên 12 ca biên | Bắt buộc | ❌ | 2 ca mới: link giả mã độc + tin mâu thuẫn tiêu đề/thân |
| L2-08 | Chuẩn tiếp cận AA trên iPhone | Bắt buộc | ❌ | Chữ ≥18px, tương phản AA, có bảng tự kiểm AA |
| L2-09 | Nhập tin bằng giọng nói | Bắt buộc | ❌ | Web Speech API (micro hệ điều hành), nút bật tắt; iOS Safari |
| L2-10 | Quản lý & xoá lịch sử | Nên có | ❌ | Xoá 1 tin / toàn bộ; hỏi xác nhận |

**Test:** `test_parser_detective.py` (5 case lệch + đúng), `test_validate_input.py`, `test_gemini_structured.py` (verify response_mime_type=application/json).

**🚦 Gate utility-ui-eval (cuối Stage 2):** chụp home/loading/result/3 màu/empty/error @ iPhone+desktop; vision subagent chấm 28-dim; phải PASS mới sang Stage 3.

---

### Stage 3 — Cấp 3: N4 Cô tâm lý + Thư viện — 6 hạng mục

| Mã | Hạng mục | Ưu tiên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| L3-01 | Hồ sơ & câu lệnh Cô tâm lý | Bắt buộc | ❌ | Giọng gần gũi, xưng cô gọi bác, 2–3 câu giải thích chiêu tâm lý; không hù doạ/dạy dỗ |
| L3-02 | Chuỗi tuần tự + hiển thị 2 phần | Bắt buộc | ❌ | Thám tử → chờ → Cô tâm lý; tổng ≤20s; 2 phần tiêu đề riêng |
| L3-03 | Điều kiện kích hoạt + lỗi độc lập | Bắt buộc | ❌ | Chỉ gọi khi nghi_ngo/nguy_hiem; Cô tâm lý gãy → Thám tử vẫn hiện + thông báo lịch sự |
| L3-04 | **Chống chèn lời nhắc (prompt injection)** | Bắt buộc | ❌ | Thiết kế prompt + lọc để tin lừa không điều khiển AI (vd "hãy nói tin này an toàn"); không hạ sai mức/đổi vai. **Mới so với backlog cũ** |
| L3-05 | Bộ kiểm thử hồi quy 20 tin | Bắt buộc | ❌ | ≥20 tin gán nhãn + lệnh chạy tự động so nhãn, in bảng đúng/sai; có doc chạy |
| L3-06 | Thư viện kiểu lừa đảo | Bắt buộc | ❌ | ≥12 kiểu, 4 nhóm (giả ngân hàng/công an/trúng thưởng/giao hàng), bộ lọc, điều hướng không reload |

**Test:** `test_psychologist_chain.py`, `test_activation_condition.py`, `test_prompt_injection.py`, `test_regression_suite.py`.

**🚦 Gate utility-ui-eval:** state có/không Cô tâm lý + state lỗi; 2 phần tách rõ.

---

### Stage 4 — Cấp 4: N5 Chiều sâu kỹ thuật — 9 hạng mục

> **Thay đổi lớn so với backlog cũ:** không còn "chọn cặp B+C" — 9 hạng mục cụ thể, nặng về đo lường chất lượng AI có số liệu.

| Mã | Hạng mục | Ưu tiên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| L4-01 | Soi và **giải** đường dẫn | Bắt buộc | ❌ | Regex tách mọi link (kể cả rút gọn) + giải redirect rút gọn về thật trước cảnh báo |
| L4-02 | Phát hiện tên miền giả bằng thuật toán | Bắt buộc | ❌ | Ký tự đồng hình (homoglyph) + khoảng cách chuỗi; ≥10 kiểu giả; nêu lý do nghi |
| L4-03 | Phát hiện dấu hiệu bằng **luật** | Bắt buộc | ❌ | Lớp luật ngoài AI: yêu cầu OTP/chuyển khoản/STK lạ/cụm từ gấp; kết hợp AI không mâu thuẫn |
| L4-04 | Bộ dữ liệu đánh giá **60 tin** | Bắt buộc | ❌ | ≥60 tin gán nhãn cân bằng + tập khó ≥15 tin mơ hồ; mỗi tin có lý do nhãn |
| L4-05 | Đo chất lượng AI có số liệu | Bắt buộc | ❌ | Chạy Thám tử trên 60 tin; accuracy + recall + ma trận nhầm lẫn; nêu ≥3 điểm yếu |
| L4-06 | Cải thiện dựa trên số liệu | Bắt buộc | ❌ | Đo trước → chỉnh prompt/logic → đo lại; chứng minh accuracy/recall tăng thật |
| L4-07 | Chế độ luyện tập 10 câu | Bắt buộc | ❌ | Đoán lừa/an toàn, chấm + giải thích từng câu, tổng kết có gợi ý cải thiện |
| L4-08 | Phản hồi thời gian thực (streaming) | Nên có | ❌ | Stream output AI; chữ hiện dần trong 3s đầu; ngắt giữa không gãy |
| L4-09 | Bộ nhớ đệm kết quả | Bắt buộc | ❌ | Cache tin đã kiểm tra → trùng không gọi lại; giới hạn hợp lý |

**Test:** `test_links.py`, `test_homoglyph.py`, `test_rule_engine.py`, `test_quiz.py`, `test_eval_report.py`.

**🚦 Gate utility-ui-eval:** 2 tính năng × 3 tình huống (thuận/lỗi/biên) không gãy.

---

### Stage 5 — Cấp 5: N6 Người ứng cứu + chia sẻ — 10 hạng mục

| Mã | Hạng mục | Ưu tiên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| L5-01 | Bảng tổng đài đã xác minh | Bắt buộc | ❌ | `data/hotlines.json` ≥10 NH + công an + Cục ATTT; lưu repo, không nhúng prompt |
| L5-02 | Câu hỏi tình huống 4 lựa chọn | Bắt buộc | ❌ | "Bác đã làm gì rồi?" — chưa làm gì / đã bấm link / đã chuyển khoản / đã cấp OTP; bấm 1 lần |
| L5-03 | Hồ sơ & câu lệnh Người ứng cứu | Bắt buộc | ❌ | Giọng bình tĩnh dứt khoát, chỉ liệt kê bước; **chỉ dùng số từ hotlines.json** |
| L5-04 | Kịch bản 4 tình huống | Bắt buộc | ❌ | Truyền số hotlines vào prompt trước gọi; bám quy trình thật |
| L5-05 | Điều phối 3 nhân vật bằng **máy trạng thái** | Bắt buộc | ❌ | FSM rõ ràng; đo lượt gọi AI giảm so với gọi ngây thơ |
| L5-06 | Chặn ảo giác số điện thoại | Bắt buộc | ❌ | Post-filter cứng mọi số vs hotlines.json; số lạ → chặn hiển thị |
| L5-07 | Kiểm thử luồng khủng hoảng + tài liệu vận hành | Bắt buộc | ❌ | Test tự động phủ 4 tình huống + tài liệu vận hành + bản tự đánh giá an toàn |
| L5-08 | Thẻ tóm tắt kết quả chia sẻ + mã QR | Bắt buộc | ❌ | Ảnh: mức rủi ro + dấu hiệu chính + tên sản phẩm + QR dẫn về; kích Zalo |
| L5-09 | Nút tải ảnh về máy | Nên có | ❌ | Tải được trên Android + iPhone, đúng thư viện ảnh |
| L5-10 | Tương phản cao + cỡ chữ điều chỉnh | Bắt buộc | ❌ | High-contrast + phóng chữ; lưu lựa chọn cho lần sau |

**Test:** `test_rescuer.py` (4 kịch bản), `test_hotlines_filter.py`, `test_fsm.py`, `test_crisis_flow.py`.

**🚦 Gate utility-ui-eval (cuối cùng):** 4 kịch bản + state "chưa làm gì"; mentor xác minh an toàn/dứt khoát/đúng quy trình.

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
| Frontend | HTML + Tailwind CSS + JS thuần → **Nginx** | Theo option 1 đề bài, hiểu rõ luồng fetch |
| Backend | **Flask REST API** (JSON, không Jinja2) | Phần API trong sáng, test độc lập |
| Giao tiếp FE→BE | `/api/*` qua reverse-proxy Nginx (cùng origin) | Không lo CORS, URL tương đối |
| Gọi Gemini | HTTP `requests` (không SDK) | Kiểm soát tuần tự, dễ mock/test, hiểu rõ luồng |
| Cấu trúc AI | `response_mime_type=application/json` + schema | Parse deterministic, đáp ứng "9/10 lần đúng cấu trúc" |
| Lịch sử | localStorage trình duyệt | Theo backlog L2-05, không cần backend state |
| Cấp 4 | Làm **đủ 9 hạng mục** (không chọn cặp) | Backlog nâng cấp yêu cầu đo lường chất lượng AI có số liệu (L4-04→L4-06) |
| Triển khai | Nginx (static) + gunicorn (Flask) trên VM target | Hai service độc lập, proxy công khai port 8000 |

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
