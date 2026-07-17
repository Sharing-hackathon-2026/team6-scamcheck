# ScamCheck — Kiến trúc hệ thống (ARCHITECTURE)

> Bổ sung cho `PLAN.md`. Mô tả cấu trúc thư mục, danh sách file cơ bản, bố cục
> hàm và luồng dữ liệu.
>
> **Kiến trúc tách 2 phần** (monorepo, dễ bảo trì):
> - **Frontend** (`frontend/`): HTML + CSS token hoá + JavaScript thuần → phục vụ bởi **Nginx**.
> - **Backend** (`backend/`): **Python Flask REST API** trả JSON thuần (không Jinja2).
> - **SQLite**: persistent cache + metadata lịch sử gọi AI theo session; WAL dùng chung giữa worker.
> - AI là **Google Gemini** qua HTTP (`requests`).
>
> Trình duyệt và Flask **cùng origin**: Nginx phục vụ static ở `/` và reverse-proxy
> `/api/*` → Flask. Frontend gọi `fetch('/api/...')` → không lo CORS.

---

## 1. Sơ đồ luồng dữ liệu (toàn hệ thống ở Cấp 5)

```
┌───────────────┐  1. fetch('/api/check', {text})      ┌───────────────────────┐
│   Trình duyệt │ ──────────────────────────────────▶ │ Edge SSL → Nginx      │
│  (iPhone 45+) │                                       │  • static frontend/   │
│               │  6. render DOM (JS)                   │  • /api/* → proxy     │
│  localStorage │ ◀────────────── JSON ────────────────┤ :8000 app · :8001 auth│
│   (history)   │                                       └──────────┬────────────┘
└───────┬───────┘                                                  │ 2. proxy_pass
        │ 2b. fetch('/api/rescue', {situation})                     ▼
        ▼                                              ┌────────────────────────┐
┌────────────────┐   3. sequential AI calls (requests) │  Flask REST API        │
│  Flask /api/   │ ──── 3a. Thám tử ──────────────────▶│  (gunicorn, :5000)     │
│   check,rescue │      (chờ kết quả)                  │   app/routes/blueprints│
│                │ ──── 3b. Cô tâm lý ───────────────▶│   app/services/        │
│  post-filter   │      (chỉ khi nghi/nguy)            │   app/prompts/         │
│  hotlines      │ ──── 3c. Người ứng cứu ───────────▶│                        │
│  strip số lạ   │      (chỉ khi user đã sa bẫy)       └───────────┬────────────┘
└────────────────┘                                                │ 4. generateContent
         ▲ 5. JSON đã parse + đã filter                           │   (JSON mode)
         └────────────────────────────────────────────────────────┘
                                              ┌────────────────────────┐
                                              │  Gemini API (HTTP)     │
                                              │ generativelanguage     │
                                              │   .googleapis.com      │
                                              └────────────────────────┘
```

**Các tầng tách biệt rõ:**
- **Frontend** chỉ lo UI + gọi API + render DOM + localStorage. Không biết gì về Gemini.
- **Backend routes** mỏng: nhận JSON → gọi services → trả JSON.
- **Services** (pure Python) chứa logic + gọi Gemini. Mỗi nhân vật AI là 1 lời gọi độc lập,
  bọc try/except riêng → một nhân vật gãy không kéo gãy cả kết quả.
- Nginx là điểm vào duy nhất của người dùng → "không cài app phía người dùng" (L1-05).

---

## 2. Cấu trúc thư mục (monorepo)

```
scamcheck/
├── frontend/                      # ⬛ HTML + CSS token hoá + JS thuần → Nginx
│   ├── index.html                 # tab Kiểm tra: input/result/rescue/share/history
│   ├── library.html               # tab Thư viện: 12 mẫu và bộ lọc riêng
│   ├── practice.html              # tab Luyện tập: 10 câu (Cấp 4-C)
│   ├── history.html               # bảng + pie chart lịch sử AI; admin Login with exe
│   ├── assets/
│   │   ├── fonts/                 # Be Vietnam Pro + Material Symbols tự host và licence
│   │   ├── css/
│   │   │   ├── tokens.css         # ⭐ foundation mint/forest/violet + light/dark/HC
│   │   │   └── app.css            # component/layout CSS ≥18px, AA contrast
│   │   └── js/
│   │       ├── config.js          # API_BASE (rỗng = cùng origin)
│   │       ├── api.js             # wrapper fetch('/api/...') + xử lý lỗi mạng
│   │       ├── app.js             # tab Kiểm tra; không import/fetch thư viện
│   │       ├── library.js         # tab Thư viện; loading/empty/error/success + retry
│   │       ├── navigation.js      # giữ aria-current tab trong vùng nhìn mobile
│   │       ├── icons.js           # map Material Symbols subset → DOM an toàn
│   │       ├── highlight-excerpts.js  # tô vàng <mark> theo excerpt (L2-04)
│   │       ├── history.js         # localStorage 10 tin gần nhất (L2-09)
│   │       ├── history-page.js    # session/universal AI metadata dashboard
│   │       ├── result-model.js    # chuẩn hoá kết quả + đúng 3 hành động
│   │       ├── rescue-model.js    # chuẩn hoá payload/response Người ứng cứu
│   │       ├── speech.js          # Web Speech API + fallback
│   │       └── practice.js        # state máy luyện tập (Cấp 4-C)
│   └── components/                # (tuỳ chọn) HTML tái dùng qua <template>/JS
│       ├── footer-legal.html      # dòng pháp lý (dùng ở mọi trang)
│       └── risk-card.html         # thẻ màu An toàn/Nghi ngờ/Nguy hiểm (tuỳ chọn)
│   ├── tests/                     # node:test cho helper JS thuần
│   ├── package.json               # scripts test/check, không dependency ngoài
│   └── ACCESSIBILITY.md           # bảng tự kiểm WCAG AA/iPhone
│
├── backend/                       # ⬛ Python Flask REST API (JSON)
│   ├── app/
│   │   ├── __init__.py            # create_app() factory + CORS tuỳ chọn
│   │   ├── config.py              # đọc env: GEMINI_API_KEY, GEMINI_MODEL...
│   │   ├── routes/                # blueprints, tiền tố /api
│   │   │   ├── __init__.py
│   │   │   ├── health.py          # GET /api/health (cho Nginx check)
│   │   │   ├── check.py           # POST /api/check → Thám tử (+Cô tâm lý Cấp 3)
│   │   │   ├── rescue.py          # POST /api/rescue → Người ứng cứu (Cấp 5)
│   │   │   ├── links_api.py       # GET /api/links-analyze (Cấp 4-B)
│   │   │   ├── quiz_api.py        # GET /api/quiz (Cấp 4-C, trả 10 tin)
│   │   │   └── ai_logs.py         # session history + exe.dev admin JSON/CSV
│   │   ├── services/              # business logic (KHÔNG import Flask, dễ test)
│   │   │   ├── gemini.py          # client HTTP Gemini (generate_json / generate_text)
│   │   │   ├── parser.py          # parse_detective/psychologist/rescuer — có fallback
│   │   │   ├── detective.py       # system prompt + gọi Thám tử
│   │   │   ├── psychologist.py    # system prompt + gọi Cô tâm lý (tuần tự)
│   │   │   ├── rescuer.py         # system prompt + gọi Người ứng cứu + post-filter
│   │   │   ├── links.py           # extract_urls() + detect_spoofed_domains()
│   │   │   ├── quiz.py            # nạp quiz.json
│   │   │   ├── storage.py         # SQLite WAL: TTL cache + AI metadata logs
│   │   │   └── validation.py      # validate_input(): rỗng, >5000 ký tự
│   │   └── prompts/               # system prompts tách riêng (text)
│   │       ├── detective.txt
│   │       ├── psychologist.txt
│   │       └── rescuer.txt
│   ├── data/                      # dữ liệu tĩnh (KHÔNG qua AI)
│   │   ├── legit_domains.json     # Cấp 4-B: whitelist tên miền chính thống
│   │   ├── quiz.json              # Cấp 4-C: 10 tin đã gán nhãn
│   │   └── hotlines.json          # Cấp 5: ≥10 ngân hàng + công an + Cục ATTT
│   ├── tests/                     # pytest — MỌI hàm trong services/ đều có test
│   │   ├── conftest.py            # fixture: mock Gemini HTTP, Flask client
│   │   ├── test_gemini_client.py
│   │   ├── test_parser_detective.py
│   │   ├── test_parser_psychologist.py
│   │   ├── test_parser_rescuer.py
│   │   ├── test_activation_condition.py
│   │   ├── test_psychologist_chain.py
│   │   ├── test_validation.py
│   │   ├── test_links.py
│   │   ├── test_quiz.py
│   │   ├── test_hotlines_filter.py
│   │   └── test_routes.py
│   ├── requirements.txt           # flask, requests, gunicorn, flask-cors, pytest
│   ├── pytest.ini
│   ├── run.py                     # entrypoint dev: python run.py → :5000
│   └── scamcheck-backend.service  # systemd unit (gunicorn)
│
├── deploy/                        # cấu hình hạ tầng triển khai
│   └── nginx.conf                 # phục vụ frontend/ + proxy /api/* → 127.0.0.1:5000
├── .env.example                   # mẫu env backend (KHÔNG có key thật)
├── .gitignore
├── README.md
├── PLAN.md
├── DESIGN_REFERENCE.md            # số đo/palette/type/layout từ site tham khảo + giới hạn licence
└── ARCHITECTURE.md                # file này
```

> Lịch sử (history) nằm ở **localStorage trình duyệt**, không ở backend — đúng backlog L2-09.
>
> **Quiz.json** được backend phục vụ qua `/api/quiz` (hoặc frontend fetch trực tiếp
> nếu muốn tĩnh hoàn toàn — quyết định khi làm Cấp 4-C).

---

## 3. Bố cục hàm (core functions)

### 3.1 `backend/app/services/gemini.py` — client HTTP Gemini
```python
def generate_json(system_prompt: str, user_prompt: str,
                  schema: dict | None = None) -> dict:
    """
    Gọi Gemini generateContent với response_mime_type=application/json.
    Trả dict đã parse. Ném GeminiError khi lỗi mạng/HTTP/parse.
    Dùng session + timeout để kiểm soát.
    """

def generate_text(system_prompt: str, user_prompt: str) -> str:
    """ Cấp 1: trả văn bản thô. """
```

### 3.2 `backend/app/services/parser.py` — parse có dự phòng (L2-02)
```python
RISK_LEVELS = {"an_toan", "nghi_ngo", "nguy_hiem"}

def parse_detective(raw: dict) -> DetectiveResult:
    """
    Validate + coerce JSON của Thám tử. Nếu lệch → trả giá trị mặc định an toàn
    (risk_level='nghi_ngo', red_flags=[], actions=[...]). KHÔNG ném lỗi app.
    """

def parse_psychologist(raw: dict) -> PsychologistResult | None:
    """ 2–3 câu, fallback 'Cô tâm lý đang bận...'. """

def parse_rescuer(raw: dict) -> RescueResult:
    """ Danh sách bước + câu nói mẫu. """
```

### 3.3 `backend/app/services/validation.py`
```python
MAX_LEN = 5000

def validate_input(text: str) -> list[str]:
    """ Trả danh sách lỗi thân thiện: rỗng, quá dài. """
```

### 3.4 `backend/app/services/links.py` (Cấp 4-B)
```python
URL_RE = re.compile(...)  # bắt http(s), bit.ly, t.co ...

def extract_urls(text: str) -> list[str]: ...

def detect_spoofed_domains(urls: list[str],
                            whitelist: list[str]) -> list[Warning]: ...
```

### 3.5 `backend/app/services/rescuer.py` (Cấp 5)
```python
def build_rescue_pipeline(situation: str, hotlines: list[Hotline]) -> RescueResult:
    """ 1) load hotlines.json → 2) gọi AI (chỉ số trong whitelist) → 3) post-filter """

def strip_unknown_phones(text: str, whitelist: set[str]) -> str:
    """ RÀNG BUỘC NGHIÊM: xoá mọi số không có trong whitelist. """
```

### 3.6 Backend routes (REST, trả JSON)
```python
# health.py
@bp.get("/api/health") -> {"ok": True}            # Nginx healthcheck

# check.py
@bp.post("/api/check")
def check():
    body = request.get_json()
    errors = validate_input(body["text"])
    if errors: return jsonify({"errors": errors}), 400      # L2-08
    det = call_detective(text)                              # bọc try → fallback parser
    psy = call_psychologist(text) if det.risk_level in {"nghi_ngo","nguy_hiem"} else None  # L3-03
    return jsonify({"detective": det.to_dict(), "psychologist": psy and psy.to_dict()})

# rescue.py
@bp.post("/api/rescue")
def rescue():
    situation = request.get_json()["situation"]           # 1 trong 4 lựa chọn
    if situation == "chua_lam_gi":
        return jsonify({"praise": "..."})                  # L5-05, không gọi AI
    result = build_rescue_pipeline(situation, load_hotlines())
    return jsonify({"rescue": result.to_dict()})
```

### 3.7 Frontend `assets/js/api.js` — wrapper fetch
```javascript
const API_BASE = ''; // cùng origin qua Nginx proxy
export async function check(text) {
  const r = await fetch(API_BASE + '/api/check', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text})
  });
  if (!r.ok) throw new Error('network');
  return r.json(); // {detective, psychologist}
}
export async function rescue(situation) { /* tương tự /api/rescue */ }
```

---

## 4. Mô hình dữ liệu

### 4.1 DetectiveResult (Thám tử)
```python
@dataclass
class RedFlag:
    label: str          # "Yêu cầu mã OTP"
    excerpt: str        # "gửi mã xác thực" (đoạn trong tin gốc để tô vàng)
    explanation: str
@dataclass
class DetectiveResult:
    risk_level: Literal["an_toan","nghi_ngo","nguy_hiem"]
    reason: str
    red_flags: list[RedFlag]
    actions: list[str]  # đúng 3 hành động
```

### 4.2 PsychologistResult (Cô tâm lý)
```python
@dataclass
class PsychologistResult:
    message: str        # 2–3 câu, giọng cô–bác
```

### 4.3 RescueResult (Người ứng cứu)
```python
@dataclass
class RescueStep:
    step: int
    action: str         # "Gọi tổng đài VCB 1900xxxx"
    script: str         # câu nói mẫu khi gọi điện
@dataclass
class RescueResult:
    situation: str
    steps: list[RescueStep]
```

### 4.4 Dữ liệu tĩnh (`backend/data/`)
- `hotlines.json`: `[{ "name": "Vietcombank", "phone": "1900545...", "type": "bank" }, ...]`
- `quiz.json`: `[{ "text": "...", "is_scam": true, "reason": "..." }, ...]` (10 mục)
- `legit_domains.json`: `{ "banks": ["vietcombank.com.vn", ...], "gov": [...] }`

---

## 5. Bảo mật & tuân thủ đề bài

1. **Khóa bí mật**: `GEMINI_API_KEY` chỉ ở env/`.env` (`.env` trong `.gitignore`).
   Pre-commit / CI check `git log -p | grep GEMINI_API_KEY` = rỗng. (L1-01, tiêu chí Cấp 1)
   → Key **chỉ tồn tại ở backend**, frontend không bao giờ thấy.
2. **Pháp lý**: footer pháp lý nhúng trong mọi trang frontend (`components/footer-legal.html`). (L1-04)
3. **Cấp 5 — không AI tự sinh số**: `strip_unknown_phones()` post-filter mọi số;
   chỉ số trong `backend/data/hotlines.json` được giữ. (L5-03/L5-04)
4. **Lịch sử kết quả người dùng** vẫn ở `localStorage`; backend chỉ persist metadata AI theo
   session và typed cache trong SQLite. Universal history/export yêu cầu Login with exe tại
   `:8001` và email trong `ADMIN_ALLOWED_EMAILS` (allowlist rỗng = fail closed).
5. **Đầu vào**: giới hạn ≤5000 ký tự + không rỗng (backend validate).
6. **CORS**: vì cùng origin qua Nginx, **không cần CORS** trong cấu hình chuẩn. Chỉ bật
   `flask-cors` khi dev tách port (frontend `:5500`, backend `:5000`).

---

## 6. Tách tầng & kiểm thử

- **Nginx**: chỉ lo phục vụ static + reverse-proxy. Không logic.
- **Frontend**: HTML/CSS/JS thuần. Test thủ công + gate `utility-ui-eval` (screenshot).
- **Backend routes** (Flask) chỉ lo HTTP + gọi service + trả JSON. Mỏng.
- **Services** (pure Python) chứa logic + gọi Gemini. **KHÔNG import Flask** → test bằng pytest
  với HTTP mock (monkeypatch `requests`), không cần chạy server.
- **Parser** thuần function `(dict)->(dataclass)`, test 5 case lệch cấu trúc + case đúng (L2-02).
- Mọi hàm public có test (quy định dự án). CI: `pytest -q` phải xanh trước mỗi stage gate.

---

## 7. UI/Design — tích hợp 2 skill

### 7.1 anti-ai-design (thiết kế)
- Chạy ở **đầu Stage 2** và mỗi lần thêm màn hình mới (Cấp 3/4/5).
- Chốt: **platform** = mobile (iPhone Safari chuẩn) + desktop responsive;
  **color** = palette tin cậy + 3 màu ngữ nghĩa risk (AA contrast);
  **style** = thân thiện người 45+ (chữ to, nút to, khoảng trắng, không rối).
- Output: đóng băng **foundation tokens** → `frontend/assets/css/tokens.css`
  (font-size ≥18px, spacing, màu risk, bo góc, shadow...).
- Bất kỳ CSS nào đều tham chiếu tokens, không hardcode → giữ nhất quán xuyên suốt.
- Redesign hiện tại dùng direction **official editorial utility** đo từ Own Your Online:
  mint canvas, forest ink, violet brand/action và broad curved landmarks; số đo và giới hạn
  sao chép/licence nằm ở `DESIGN_REFERENCE.md`.
- IA một tác vụ mỗi URL: `/` check/rescue/share, `/library.html` thư viện, `/practice.html`
  quiz. Đây là real links với `aria-current`, không phải tab giả hoặc SPA state.
- Galano Grotesque là font thương mại nên không scrape/hotlink. Frontend self-host Be Vietnam
  Pro (OFL) và một subset Material Symbols Rounded (Apache 2.0), không request font/icon runtime.
- `color-scheme` cùng `@media (prefers-color-scheme: dark)` tự theo hệ điều hành; high contrast
  và chữ 100/115/130% là preference đọc riêng. Semantic safe/warning/danger giữ contrast AA.
- Result ưu tiên verdict → ba hành động ngay → bằng chứng; technical analysis là disclosure.
  Thư viện có URL/module/loading/empty/error/retry riêng; quiz có semantic progress, retry
  counted và completion.

### 7.2 utility-ui-eval (gate UX)
- Gate **chặn** ở **cuối mỗi Stage 2–5**.
- Orchestrator CHỈ: (a) chụp screenshot các state (home/loading/result/3 màu/empty/error/4 tình huống)
  ở viewport iPhone + desktop; (b) spawn **vision-capable subagent** với rubric 28-dimension;
  (c) **không tự chấm**, hành động theo verdict.
- Phải PASS §1–§15 (comprehension) VÀ §16–§28 (null-interaction / fake-functionality).
- Nếu BLOCKED (không có vision subagent) → báo rõ, không bịa điểm.

---

## 8. Triển khai (deploy)

### Dev
- **Frontend:** mở `frontend/index.html` qua static server (vd `python -m http.server` ở `:5500`,
  hoặc Live Server). `config.js` trỏ `API_BASE = 'http://localhost:5000'` (dev tách port).
- **Backend:** `python backend/run.py` → `http://localhost:5000`. CORS bật cho `:5500`.

### Prod (VM deploy target)
- **VM:** `team6-scamcheck.exe.xyz`.
- **Public URL:** `https://team6-scamcheck.exe.xyz/` (full SSL; edge tự forward tới Nginx port `8000`).
- **Nginx** (trong VM, hoặc do proxy exe.dev đảm nhiệm) phục vụ `frontend/` tại `/`
  VÀ reverse-proxy `/api/*` → `127.0.0.1:5000` (Flask/gunicorn).
- **Flask** chạy gunicorn port nội bộ `:5000`, systemd unit `backend/scamcheck-backend.service`.
- Env `GEMINI_API_KEY` qua systemd `EnvironmentFile=/etc/scamcheck.env`.
- **Hai service độc lập**: sửa frontend = reload Nginx (hoặc thậm chí chỉ cần git pull, vì static);
  sửa backend = restart gunicorn. Không ảnh hưởng lẫn nhau.

## 9. Stage 3 — chuỗi Cô tâm lý và thư viện

### 9.1 Tool-call handoff có guardrail

```text
validate + NFC
      │
      ▼
Gemini Thám tử --forced function call--> arguments DetectiveResult
                                      │
                               parser + guardrail
                                      │
                 an_toan/khong_lien_quan ─▶ psychologist_status=not_needed
                                      │
                 nghi_ngo/nguy_hiem
                                      ▼
                         Gemini Cô tâm lý
                                      │
                         parse + role guardrail
                                      │
                         ├─ thành công: message 2–3 câu
                         └─ lỗi: trạng thái độc lập, giữ nguyên Thám tử
```

- Thám tử phải gọi một trong hai function declaration: `complete_detective` hoặc
  `handoff_to_psychologist`; cả hai dùng cùng schema DetectiveResult.
- Backend không tin tên tool: parser/guardrail có quyền đổi verdict và quyết định
  có gọi Cô tâm lý hay không. Prompt injection không thể tự bật/tắt pipeline.
- Đây là terminal handoff: không gửi function response về Thám tử, không có lượt
  tổng hợp cuối vì frontend tự render hai payload có kiểu rõ ràng.
- Cô tâm lý nhận tin gốc dưới khối dữ liệu không tin cậy và verdict đã parse.
- Hai model call không chạy song song vì Cô tâm lý phụ thuộc verdict; tin an toàn
  tốn 1 lượt, tin nghi ngờ/nguy hiểm tối đa 2 lượt.
- Budget thời gian: Thám tử 6s, một retry; Cô tâm lý 5s, không retry.
- Không có quota theo phiên; audit vẫn giữ tối đa 10 metadata persona invocation gần nhất.

### 9.2 Contract bổ sung

```json
{
  "detective": { "risk_level": "nguy_hiem", "reason": "...", "red_flags": [], "actions": [] },
  "psychologist": { "message": "Cô hiểu vì sao tin này dễ làm bác lo..." },
  "psychologist_status": "complete | not_needed | unavailable",
  "psychologist_error": null
}
```

### 9.3 Thư viện lừa đảo

- JSON tĩnh tại `backend/data/scam_library.json`, đúng bốn nhóm và ít nhất 12 mẫu.
- `GET /api/scam-library` trả dữ liệu đã validate; không gọi AI.
- UI lọc theo nhóm và URL hash ở client, không reload; hỗ trợ bàn phím/focus.

### 9.4 Bộ hồi quy

- `backend/data/regression_messages.json`: 20 tin có nhãn và lý do.
- `backend/scripts/run_regression.py`: runner thật, in bảng đúng/sai và tổng kết.
- Unit test dùng predictor giả để kiểm tra loader/evaluator/report mà không gọi Gemini.

> Dev/scaffold/test chạy trên VM hiện tại; chỉ ship bản chạy được lên VM target.
>
> Cấu hình Nginx mẫu (`deploy/nginx.conf`):
> ```nginx
> server {
>     listen 8000;
>     root /opt/scamcheck/frontend;        # web root = thư mục frontend
>     index index.html;
>     location /api/ { proxy_pass http://127.0.0.1:5000; }   # → Flask
>     location / { try_files $uri /index.html; }              # SPA-friendly fallback
> }
> ```

Tương đương Render/Railway trong đề bài; đảm bảo "không cài app phía người dùng".

## 10. Stage 4 — kiến trúc chiều sâu kỹ thuật

Phần này là thiết kế triển khai cho Stage 4; các tên file Stage 4 trong sơ đồ thư mục
ở trên là đích kiến trúc, không phải mô tả nhầm của Stage 3.

### 10.1 Pipeline kiểm tra sau Stage 4

```text
normalize + validate
      │
      ├─ SHA-256(normalized text + model + pipeline version)
      │       └─ cache hit: trả kết quả typed, không gọi AI/không lưu plaintext server
      │
      ├─ extract/normalize URL
      │       ├─ URL thường: phân tích domain tại chỗ
      │       └─ shortener: resolve tối đa 3 redirect
      │              └─ chặn scheme lạ + private/loopback/link-local/reserved IP mỗi hop
      │
      ├─ domain detector
      │       └─ IDN/punycode + zero-width + confusable skeleton + edit distance
      │
      ├─ pure rule engine
      │       └─ OTP/credential/tiền/STK/khẩn cấp/URL đáng ngờ theo từng mệnh đề
      │
      ├─ Gemini Thám tử terminal function call
      │
      ├─ parser + merge policy bảo thủ
      │       ├─ danger rule: verdict cuối = nguy_hiem
      │       └─ warning rule: không cho an_toan/khong_lien_quan, nâng tối thiểu nghi_ngo
      │
      ├─ Cô tâm lý nếu verdict cuối nghi_ngo/nguy_hiem
      └─ cache kết quả hoàn chỉnh + trả technical_analysis và cache metadata
```

### 10.2 URL/SSRF và tên miền giả

- `services/links.py` chỉ nhận HTTP/HTTPS, bỏ fragment, chuẩn hoá host bằng IDNA.
- Chỉ shortener trong allowlist mới được gọi mạng; URL thường không bị backend truy cập.
- Trước **mỗi redirect hop**, resolver kiểm tra mọi địa chỉ DNS. Chỉ địa chỉ public
  (`ipaddress.is_global`) được phép; chặn localhost, private, loopback, link-local,
  multicast, reserved và URL có user-info.
- Request redirect dùng timeout ngắn, `allow_redirects=False`, `stream=True`, không đọc body,
  giới hạn hop và đóng response ngay. Lỗi resolve là warning bảo thủ, không làm gãy `/api/check`.
- `data/legit_domains.json` là allowlist có brand, domain chính thức, nguồn và ngày review.
  Detector không tự tuyên bố chắc chắn lừa đảo: nó trả lý do heuristic có cấu trúc.

### 10.3 Rule engine và merge policy

- `services/rule_engine.py` là pure functions; phủ OTP/PIN/password, dữ liệu cá nhân,
  yêu cầu tiền, số tài khoản, thúc giục/đe doạ và URL đáng ngờ.
- Phủ định được xét trong cùng câu/mệnh đề, không dùng một câu “không gửi OTP” để
  vô hiệu hoá yêu cầu “hãy gửi OTP” ở câu sau.
- Rule signal có `code`, `severity`, `label`, `excerpt`, `explanation`; excerpt luôn là
  lát cắt thật từ input.
- Rule nguy hiểm có quyền nâng verdict nhưng không hạ verdict AI. Signal cảnh báo chỉ
  nâng nhãn lạc quan lên `nghi_ngo`. Frontend hiển thị riêng nguồn kỹ thuật, không giả
  là kết luận chắc chắn của một heuristic.

### 10.4 Cache và quyền riêng tư

- Cache backend nằm trong SQLite WAL, bounded mặc định 256 mục/1 giờ và dùng chung giữa hai
  gunicorn worker; restart/deploy không làm mất cache còn TTL.
- Key là SHA-256 của NFC input cùng model và `STAGE4_PIPELINE_VERSION`; value là payload typed.
  Không log cache key như định danh người dùng; không cache lỗi Detective hoặc kết quả Cô tâm lý
  `unavailable` để tránh giữ lỗi tạm thời.
- `ai_request_logs` chỉ lưu timestamp, actor, status, risk, input length, summary và session id
  ngẫu nhiên; không lưu source message/prompt/OTP. Retention mặc định 30 ngày.
- Frontend vẫn giữ lịch sử kết quả plaintext tối đa 10 mục trên thiết bị theo yêu cầu sản phẩm.

### 10.5 Đo chất lượng

- `data/evaluation_messages.json`: ít nhất 60 tin cân bằng bốn nhãn, có dev/eval split
  và tối thiểu 15 ca khó.
- `services/evaluation.py` sinh accuracy, precision/recall/F1 từng lớp, confusion matrix,
  latency và invalid/fallback rate.
- `scripts/run_stage4_evaluation.py` hỗ trợ `--prompt-mode stage3|stage4`, throttle mặc
  định 4,2 giây để không vượt rate limit. Report chính so baseline Stage 3 với prompt
  scope Stage 4 + URL/domain/rules; mỗi run dùng cùng 60 ca và ghi invalid rate để không
  che lỗi provider. Khi chỉ đo tác động rule, cùng raw output trong một run vẫn được chấm
  baseline/improved để giảm nhiễu model.
- Report ghi model, prompt/pipeline version, commit và timestamp; JSON machine-readable
  đi cùng Markdown để review.

### 10.6 Luyện tập và phản hồi tiến trình

- `GET /api/quiz` phục vụ 10 câu curated, không gọi AI. `practice.html` + `practice.js`
  quản lý state thật: trả lời, giải thích ngay, tổng kết, restart và bàn phím/screen reader.
- Luồng kiểm tra giữ contract JSON deterministic. UI phát các trạng thái tiến trình hữu ích
  ngay từ lúc gửi (soi link → đối chiếu dấu hiệu → chờ persona), có timeout/cancel bằng
  `AbortController`; không giả token streaming làm hỏng function-call parsing.

## 11. Stage 5 — FSM Người ứng cứu, hotline và ảnh chia sẻ

### 11.1 Máy trạng thái ba persona

```text
POST /api/check
  START
    └─ Detective (1 call)
         ├─ an_toan/khong_lien_quan ──▶ assessment_complete
         └─ nghi_ngo/nguy_hiem
              └─ Psychologist (1 call, lỗi không đổi verdict)
                   └─ awaiting_situation
                        ├─ chua_lam_gi ──▶ prevention_complete (0 Rescuer call)
                        ├─ da_bam_link ─┐
                        ├─ da_chuyen_tien ─┼─▶ Rescuer tối đa 1 call ─▶ rescue_complete
                        └─ da_cung_cap_otp ─┘         │
                                                     └─ lỗi/invalid/kill switch
                                                        └─ guarded deterministic playbook
```

Transition do `services/fsm.py` quyết định từ verdict/situation enum; function name hay text
Gemini không được chuyển state. Mỗi response có metrics so với baseline ngây thơ luôn gọi
persona kế tiếp. Với bốn situation, FSM bỏ 1/4 Rescuer call (`25%`) nhờ nhánh `chua_lam_gi`.
Cache hit ở check có `actual_ai_calls=0`.

### 11.2 Boundary dữ liệu ứng cứu

- `message_text` được NFC/length validate rồi chỉ dùng trong `match_bank_hotlines()`; toàn văn
  không đi vào prompt Rescuer. Client `red_flags` cũng bị bỏ vì có thể giả dạng dữ liệu
  riêng tư; AI chỉ nhận risk level, situation, step keys và bảng hotline public.
- `data/hotlines.json` có 10 ngân hàng, Công an và tổng đài 156; mỗi entry có URL official
  theo từng số, evidence quote và ngày kiểm tra. Loader còn đối chiếu chính số trong evidence,
  fail closed nếu duplicate/thiếu nhóm/bằng chứng không khớp.
- Prompt nhận bảng hotline runtime + `HOTLINE_IDS_ALLOWED_BY_STEP`; không hardcode số trong
  prompt. Parser đòi đủ ordered `REQUIRED_STEP_KEYS`, từ chối URL/email/số lạ và instruction
  bấm link/gửi OTP/cài remote/chuyển thêm tiền/trả phí thu hồi. Toàn bộ action/headline/
  reassurance/closing hiển thị lấy từ deterministic playbook; không render crisis prose AI.
- Số điện thoại được post-filter cả trong action/detail. Mảng `hotlines` public được server
  dựng lại từ dataclass trusted; frontend chỉ tạo `tel:` từ mảng này. ID hotline đúng case
  nhưng gắn sai step cũng bị loại.
- `113` có trong bảng public nhưng không tự gắn vào bốn situation vì chưa có bằng chứng nguy
  hiểm tức thời; flow chuyển tiền hướng tới cơ quan Công an gần nhất thay vì biến 113 thành
  số trình báo chung.
- `RESCUE_AI_ENABLED=false` là kill switch: ba crisis flow vẫn trả deterministic playbook,
  `guarded_fallback` và không gọi AI.

### 11.3 Share card và QR

Frontend dựng Canvas PNG 1080×1350 theo yêu cầu người dùng, không tự kéo dài result. Model
ảnh chỉ giữ risk/reason đã redact URL, email và dãy số; tối đa ba label, không giữ text gốc
hay excerpt. Web Share `File` được ưu tiên; fallback download Blob, riêng iOS cũ mở ảnh để
chạm giữ/Lưu vào Ảnh.

`GET /api/share/qr.svg` không nhận URL tùy ý; base URL/Host phải thuộc
`SHARE_ALLOWED_HOSTS`, production phải HTTPS. Encoder standard-library tạo QR Version 3-L,
byte mode, Reed–Solomon 15 codewords, mask 0, quiet zone 4 module; SVG same-origin được
frontend decode module và vẽ trực tiếp vào PNG. Matrix đã được test byte-for-byte với
implementation QR độc lập trong bước verification, không thêm dependency runtime/CDN.

### 11.4 Preference accessibility

`preferences.js` dùng một schema localStorage fail-safe cho high contrast và font scale
100%/115%/130% trên cả main/practice. Inline head bootstrap chỉ áp giá trị allowlist để giảm
flash; module vẫn normalize lần nữa. System `prefers-color-scheme` tiếp tục quyết định
light/dark, hoàn toàn không có theme toggle.

Runbook vận hành và quy trình rà hotline: `backend/RESCUE_RUNBOOK.md`.
