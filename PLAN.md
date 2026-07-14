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

| Giai đoạn | Cấp | Nhóm tính năng | Mục tiêu | Skill liên quan |
|---|---|---|---|---|
| Stage 1 | Cấp 1: Bản thô | N1 | Vòng lặp cơ bản: gọi Gemini → hiện kết quả thô → lên mạng | — |
| Stage 2 | Cấp 2: Tối giản đầy đủ | N2 + N3 | Thám tử, thẻ rủi ro, tô vàng, tin mẫu, xử lý lỗi, lịch sử, UI iPhone | **anti-ai-design** (thiết lập foundation), **utility-ui-eval** (gate) |
| Stage 3 | Cấp 3: Cô tâm lý | N4 | Chuỗi 2 nhân vật AI tuần tự, xử lý lỗi độc lập | anti-ai-design, utility-ui-eval (gate) |
| Stage 4 | Cấp 4: 2 tính năng mở rộng | N5 | Tích hợp **B (Soi đường dẫn)** + **C (Chế độ luyện tập)** *(chốt ở §4)* | anti-ai-design, utility-ui-eval (gate) |
| Stage 5 | Cấp 5: Người ứng cứu | N6 | Chuỗi 3 nhân vật AI, xử lý khủng hoảng, bảng tổng đài tĩnh | anti-ai-design, utility-ui-eval (gate cuối) |
| Stage 6 | N7: Sẵn sàng trình diễn | N7 | README, sơ đồ, slide, kịch bản demo, minh chứng AI, video | — |

> Luồng Stage 6 chạy **song song** từ Stage 2.
>
> **Quyết định cặp tính năng Cấp 4** (chốt trong Stage 0, §4 dưới): chọn **B + C** (chiều sâu kỹ thuật — giám khảo cho điểm cao hơn cho tính năng làm *sâu*). A và D nằm trong phần "vượt cấp" nếu còn thời gian.

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

### Stage 0 — Khởi tạo (ngày khởi động)

**Mục tiêu:** Nền móng repo, config, CI tối thiểu, chốt lựa chọn Cấp 4.

- [x] ~~Tạo repo~~ Repo `Sharing-hackathon-2026/team6-scamcheck` (remote có sẵn).
- [x] `.gitignore` (loại trừ `.env`, `__pycache__`, `venv`, `*.db`).
- [x] `.env.example` (không chứa key thật) + hướng dẫn điền key.
- [x] Cấu trúc thư mục monorepo (frontend/ + backend/) + Flask skeleton.
- [x] `backend/requirements.txt`, `backend/pytest.ini` (28 test xanh).
- [x] **Chốt cặp tính năng Cấp 4 = B + C** (ghi trong §4).
- [x] `requests` + verify key thật `gemini-3.1-flash-lite` gọi OK.

**Hoàn thành:** Repo chạy `flask run` lên trang trắng với footer pháp lý. Key không lộ trong git history (`git log -p | grep GEMINI_API_KEY` = rỗng).

---

### Stage 1 — Cấp 1: Bản thô (N1)

**Mục tiêu kỹ năng:** Chứng minh gọi được Gemini và đưa 1 trang web lên mạng.

Backlog mapping: **L1-01 → L1-05**.

- [x] **L1-01** Khởi tạo kho mã — `.gitignore` + `.env.example` (đã làm ở Stage 0, verify lại).
- [x] **L1-02** Giao diện nhập liệu cơ bản — `frontend/index.html`: `<textarea>` lớn + nút **Kiểm tra**, footer pháp lý. Chưa cần đẹp.
- [x] **L1-03** Tích hợp Gemini — `POST /api/check` (Flask) gọi `services/gemini.py:generate_text()`, trả **JSON** `{"result": "..."}`; JS `app.js` fetch rồi hiện văn bản thô.
- [x] **L1-03b** Harden Stage 1 — `app/prompts.py:STAGE1_SYSTEM_PROMPT` định nghĩa vai ScamCheck + quy tắc **từ chối** tin không liên quan (trả canned `STAGE1_REFUSAL`), giới hạn output ≤120 từ → tránh lãng phí quota khi user dán tin thường. Verify AI thật: 3 tin thường → refusal, 4 tin lừa đảo (gồm giả danh người quen xin tiền) → phân tích đúng.
- [x] **L1-04** Dòng cảnh báo pháp lý — component footer HTML ở mọi trang frontend.
- [x] **L1-05** Triển khai lên mạng ✅ — Nginx phục vụ `frontend/` + reverse-proxy `/api/*` sang gunicorn(Flask) trên VM `team6-scamcheck.exe.xyz`. Địa chỉ công khai: **https://team6-scamcheck.exe.xyz:8000/** (đã verify live).

**Test (pytest):**
- `backend/tests/test_gemini_raw.py` — mock HTTP, verify request payload đúng (key, model, prompt).
- `backend/tests/test_routes.py::test_api_check_returns_json`.
- `backend/tests/test_prompts.py` — ràng buộc nội dung system prompt (refusal canned, vai hẹp, giới hạn output).
- `backend/tests/test_routes.py::test_check_sends_hardened_system_prompt` — verify route gửi `system_prompt` đi.

**Tiêu chí hoàn thành:** Mentor mở URL trên iPhone, dán tin mẫu, thấy kết quả AI trong ≤30s. Git history sạch key.

---

### Stage 2 — Cấp 2: Tối giản đầy đủ (N2 Thám tử + N3 Trải nghiệm)

**Mục tiêu kỹ năng:** Sản phẩm cốt lõi hoàn thiện, chạy được trên iPhone của người 45+ mà không cần hướng dẫn.

> 🎨 **Gate thiết kế — anti-ai-design (BẮT BUỘC ở đầu Stage 2):** Trước khi viết CSS, kích hoạt skill để chốt:
> - **Platform:** `mobile` (iPhone Safari là chuẩn chấm điểm) + responsive `desktop`.
> - **Color direction:** palette tin cậy + 3 màu ngữ nghĩa (An toàn=Xanh, Nghi ngờ=Vàng, Nguy hiểm=Đỏ) ở độ tương phản AA.
> - **Style:** giao diện thân thiện người lớn tuổi — chữ to, nút to, nhiều khoảng trắng, không hiệu ứng rối.
> Đóng băng foundation tokens (font ≥18px, spacing, màu) vào `frontend/assets/css/tokens.css`.

Backlog mapping: **L2-01 → L2-10**.

**N2 — Thám tử (phân tích kỹ thuật):**
- [ ] **L2-01** Hồ sơ & system prompt Thám tử (giọng khô khan, lý tính) + **cấu trúc JSON cố định**:
  ```json
  {
    "risk_level": "an_toan" | "nghi_ngo" | "nguy_hiem",
    "reason": "tóm tắt 1 câu",
    "red_flags": [
      { "label": "Yêu cầu mã OTP", "excerpt": "gửi mã xác thực", "explanation": "..." }
    ],
    "actions": ["việc nên làm 1", "việc nên làm 2", "việc KHÔNG nên làm 3"]
  }
  ```
- [ ] **L2-02** Hàm đọc kết quả **có dự phòng** — `backend/app/services/parser.py:parse_detective()`: validate schema, coerce, fallback mặc định an toàn khi lệch. **Bắt buộc test 5 trường hợp lệch.**
- [ ] **L2-03** Thẻ màu mức rủi ro (component `_risk_card.html`).
- [ ] **L2-04** Danh sách dấu hiệu + **tô vàng đoạn trích** trong tin gốc (JS `frontend/assets/js/highlight-excerpts.js`: tìm chuỗi con, bọc `<mark>`; không tìm thấy thì bỏ qua).
- [ ] **L2-05** Danh sách 3 hành động khuyến nghị.

**N3 — Trải nghiệm người dùng cốt lõi:**
- [ ] **L2-06** 3 nút tin mẫu (giả ngân hàng, giả công an, trúng thưởng) → điền sẵn textarea.
- [ ] **L2-07** Màn hình chờ (loading lịch sự).
- [ ] **L2-08** Xử lý **5 trường hợp biên**: rỗng, >5000 ký tự, mất mạng, AI từ chối, AI trả lệch cấu trúc → thông báo thân thiện, không gãy.
- [ ] **L2-09** Lịch sử 10 tin gần nhất — **localStorage** (`frontend/assets/js/history.js`), xem lại không gọi AI lại.
- [ ] **L2-10** Giao diện thân thiện iPhone — font ≥18px, tương phản AA, layout không vỡ.

**Test (pytest):**
- `backend/tests/test_parser_detective.py` — 5 case lệch cấu trúc + case đúng.
- `backend/tests/test_validate_input.py` — rỗng, >5000 ký tự.
- `backend/tests/test_gemini_structured.py` — mock verify `response_mime_type=application/json`.

**🚦 Gate UX — utility-ui-eval (BẮT BUỘC cuối Stage 2):**
- Chụp screenshot các state (home/loading/result/3 màu rủi ro/empty/error) ở viewport iPhone + desktop.
- Spawn **vision-capable subagent** chấm 28-dimension rubric. Không tự chấm.
- Phải PASS §1–§15 (comprehension) và §16–§28 (không null interaction). Sửa cho đến khi PASS mới sang Stage 3.

**Tiêu chí hoàn thành:** 12/15 tin mẫu đúng. Mentor dùng trên iPhone thật trong 30s không hướng dẫn. 5 biên không gãy.

---

### Stage 3 — Cấp 3: Cô tâm lý (N4)

**Mục tiêu kỹ năng:** Chuỗi gọi AI tuần tự, xử lý lỗi độc lập từng tầng.

Backlog mapping: **L3-01 → L3-05**.

- [ ] **L3-01** Hồ sơ Cô tâm lý — giọng gần gũi, xưng "cô", gọi "bác", 2–3 câu giải thích chiêu thức tâm lý. System prompt riêng.
- [ ] **L3-02** Chuỗi tuần tự: Thám tử → (chờ xong) → Cô tâm lý. Hai kết quả cùng trang. Tổng ≤20s.
- [ ] **L3-03** **Điều kiện kích hoạt:** chỉ gọi Cô tâm lý khi `risk_level ∈ {nghi_ngo, nguy_hiem}`. Tin `an_toan` không tốn lượt gọi.
- [ ] **L3-04** Tách 2 phần UI rõ ràng: "Phân tích kỹ thuật" (Thám tử) + "Hiểu vì sao mình suýt tin" (Cô tâm lý).
- [ ] **L3-05** **Xử lý lỗi độc lập:** bọc try/except riêng cho Cô tâm lý; khi gãy, Thám tử vẫn hiển thị + dòng *“Cô tâm lý đang bận, vui lòng thử lại sau.”*

**Test (pytest):**
- `backend/tests/test_psychologist_chain.py` — chuỗi tuần tự đúng thứ tự, mock AI thứ 2 ném lỗi → Thám tử vẫn trả được.
- `backend/tests/test_activation_condition.py` — `an_toan` không trigger gọi thứ 2 (verify số lần gọi Gemini = 1).

**🚦 Gate UX — utility-ui-eval:** chụp state có/không Cô tâm lý + state lỗi. Xác nhận 2 phần tách rõ, không lẫn giọng.

---

### Stage 4 — Cấp 4: 2 tính năng mở rộng (N5)

> Cặp đã chốt: **B (Soi đường dẫn)** + **C (Chế độ luyện tập)**. Lý do: độ khó vừa/trung bình, thể hiện chiều sâu kỹ thuật (regex + quản lý trạng thái), giám khảo điểm cao hơn cho tính năng làm sâu.

**B — Soi đường dẫn và tên miền:**
- [ ] **L4-B1** Tách đường dẫn (`backend/app/services/links.py:extract_urls()`) — regex, bao gồm link rút gọn (bit.ly, ...). Test không sót, không nhầm text thường.
- [ ] **L4-B2** Phát hiện tên miền giả mạo — so khớp với whitelist tổ chức chính thống (`data/legit_domains.json`), cảnh báo ký tự thay thế (vd `vietcornbank`). Test ≥5 kiểu giả mạo.
- [ ] UI: khối "Soi đường dẫn" trong trang kết quả, cảnh báo **trước** khi người dùng bấm.

**C — Chế độ luyện tập:**
- [ ] **L4-C1** `data/quiz.json` — 10 tin (5 lừa đảo/5 an toàn), mỗi tin có nhãn + giải thích. Không trùng tin mẫu.
- [ ] **L4-C2** Trang `frontend/practice.html` — hiện từng câu, user đoán, chấm + giải thích ngay (JS local, không cần AI), tổng kết điểm + nhận xét.
- [ ] Điều hướng giữa trang chính ↔ luyện tập **không reload full app** (fetch/SPA nhẹ hoặc route riêng).

**Test (pytest):**
- `backend/tests/test_links.py` — extract + detect, ≥5 case giả mạo.
- `backend/tests/test_quiz.py` — tải data đúng, tính điểm đúng.

**🚦 Gate UX — utility-ui-eval:** 2 tính năng × 3 tình huống (thuận lợi/lỗi/biên) không gãy.

**Vượt cấp (tuỳ chọn, nếu còn giờ):** A (thư viện) + D (thẻ cảnh báo có QR).

---

### Stage 5 — Cấp 5: Người ứng cứu (N6)

**Mục tiêu kỹ năng:** Chuỗi 3 nhân vật AI, biến công cụ phán xét thành công cụ đồng hành xử lý khủng hoảng.

Backlog mapping: **L5-01 → L5-06**.

- [ ] **L5-01** `data/hotlines.json` — tổng đài chính thức ≥10 ngân hàng lớn + đường dây công an + Cục ATTT. **Lưu trong repo, không nhúng vào prompt.** Mentor xác minh.
- [ ] **L5-02** Câu hỏi *“Bác đã làm gì rồi?”* — 4 lựa chọn: chưa làm gì / đã bấm link / đã chuyển khoản / đã cung cấp mã OTP. Bấm 1 lần, không cho đổi.
- [ ] **L5-03** Hồ sơ Người ứng cứu — giọng bình tĩnh, dứt khoát, KHÔNG an ủi/phân tích, chỉ liệt kê bước. **Chỉ được dùng số từ `hotlines.json`.**
- [ ] **L5-04** 4 kịch bản theo lựa chọn — truyền danh sách số hotlines vào system prompt trước khi gọi. Đầu ra: danh sách bước đánh số, mỗi bước kèm câu nói mẫu khi gọi điện.
- [ ] **L5-05** Phản hồi "chưa làm gì" → lời khen ngắn, **không** gọi Người ứng cứu (tiết kiệm lượt Gemini).
- [ ] **L5-06** Test cả 4 tình huống trên Chrome + Safari iPhone.

**Bảo mật dữ liệu (RÀNG BUỘC NGHIÊM):**
- Sau mỗi phản hồi, **post-filter** mọi số điện thoại → nếu không có trong `hotlines.json` thì **loại bỏ** và thay bằng tham chiếu *“(gọi số ngân hàng in trên thẻ)”*. Đảm bảo **không số nào do AI tự sinh**.

**Test (pytest):**
- `backend/tests/test_rescuer.py` — 4 kịch bản, post-filter số lạ = rỗng.
- `backend/tests/test_hotlines_filter.py` — số trong whitelist giữ nguyên, số lạ bị strip.

**🚦 Gate UX — utility-ui-eval (CUỐI CÙNG):** chụp 4 kịch bản + state "chưa làm gì". Mentor xác minh hướng dẫn an toàn/dứt khoát/đúng quy trình.

---

### Stage 6 — N7: Sẵn sàng trình diễn (song song từ Stage 2)

- [ ] **N7-01** `README.md` (mô tả, chạy máy cá nhân, tính năng, thành viên).
- [ ] **N7-02** Sơ đồ kiến trúc (dựa trên `ARCHITECTURE.md`).
- [ ] **N7-03** Slide 8–10 trang (bài toán/giải pháp/demo/điểm kỹ thuật/bài học + dòng pháp lý).
- [ ] **N7-04** Kịch bản demo 3–5 phút.
- [ ] **N7-05** Minh chứng AI (screenshot prompt+response ≥3 tin).
- [ ] **N7-06** Video dự phòng <5 phút, offline-ready.

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
| Lịch sử | localStorage trình duyệt | Theo backlog L2-09, không cần backend state |
| Cấp 4 | **B + C** | Chiều sâu kỹ thuật, điểm giám khảo cao |
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
