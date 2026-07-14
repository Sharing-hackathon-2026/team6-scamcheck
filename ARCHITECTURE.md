:# ScamCheck — Kiến trúc hệ thống (ARCHITECTURE)

> Bổ sung cho `PLAN.md`. Mô tả cấu trúc thư mục, danh sách file cơ bản, bố cục
> hàm và luồng dữ liệu. Stack: **Python Flask + Jinja2 + Tailwind (CDN)**, AI là
> **Google Gemini** qua HTTP (`requests`).

---

## 1. Sơ đồ luồng dữ liệu (toàn hệ thống ở Cấp 5)

```
┌──────────────┐   POST /check (text)        ┌──────────────────────┐
│  Trình duyệt │ ─────────────────────────▶ │  Flask route         │
│              │                             │  /check → Service    │
│              │                             └──────────┬───────────┘
│  localStorage│                                        │
│   (history)  │ ◀──── render Jinja2 (JSON) ────────────┘
└──────┬───────┘                                                    │
       │ POST /rescue (situation)                                    │
       ▼                                                            ▼
┌─────────────┐   sequential AI calls          ┌────────────────────────┐
│ /rescue svc │ ───── 1. Thám tử ─────────────▶│ Gemini API (HTTP)     │
│             │        (chờ kết quả)            │ generativelanguage    │
│             │ ───── 2. Cô tâm lý ───────────▶│   .googleapis.com     │
│  if nghi/nguy│        (chỉ khi nghi/nguy)     │  /models/.../generate │
│             │ ───── 3. Người ứng cứu ───────▶ │  Content (JSON mode)  │
│             │        (chỉ khi user đã sa bẫy) │                       │
│ post-filter │                                 │                       │
│  hotlines   │ ◀── structured JSON ────────────┘──────────────────────┘
│ strip số lạ │
└─────────────┘
```

**Các tầng tách biệt rõ — mỗi nhân vật AI là 1 lời gọi độc lập, bọc try/except riêng.**
Một nhân vật gãy không kéo gãy cả kết quả.

---

## 2. Cấu trúc thư mục

```
scamcheck/
├── app/                          # Ứng dụng Flask (package)
│   ├── __init__.py               # create_app() factory
│   ├── config.py                 # đọc env: GEMINI_API_KEY, MODEL, BASE_URL...
│   ├── routes/                   # route handlers (blueprints)
│   │   ├── __init__.py
│   │   ├── main.py               # GET /  (home: textarea + 3 tin mẫu + footer)
│   │   ├── check.py              # POST /check → gọi Thám tử (+Cô tâm lý ở Cấp 3)
│   │   ├── rescue.py             # POST /rescue → Người ứng cứu (Cấp 5)
│   │   ├── practice.py           # GET /practice → chế độ luyện tập (Cấp 4-C)
│   │   └── links_api.py          # GET /api/links-analyze (Cấp 4-B, tuỳ chọn fetch)
│   ├── services/                 # business logic (KHÔNG import Flask, dễ test)
│   │   ├── gemini.py             # client HTTP gọi Gemini (generate_json)
│   │   ├── parser.py             # parse_detective() / parse_psychologist() / parse_rescuer() — có fallback
│   │   ├── detective.py          # system prompt + gọi Thám tử
│   │   ├── psychologist.py       # system prompt + gọi Cô tâm lý (tuần tự sau Thám tử)
│   │   ├── rescuer.py            # system prompt + gọi Người ứng cứu + post-filter hotlines
│   │   ├── links.py              # extract_urls() + detect_spoofed_domains()
│   │   ├── quiz.py               # nạp/correct quiz (Cấp 4-C)
│   │   └── validation.py         # validate_input(): rỗng, >5000 ký tự...
│   ├── prompts/                  # system prompts tách riêng (chuỗi text)
│   │   ├── detective.txt
│   │   ├── psychologist.txt
│   │   └── rescuer.txt
│   ├── templates/                # Jinja2
│   │   ├── base.html             # <html> + <head> + footer pháp lý cố định
│   │   ├── home.html             # textarea + 3 nút tin mẫu
│   │   ├── result.html           # thẻ rủi ro + dấu hiệu tô vàng + hành động (+ Cô tâm lý +rescue)
│   │   ├── practice.html         # luyện tập 10 câu
│   │   └── partials/
│   │       ├── _legal.html       # dòng pháp lý (dùng ở mọi màn hình)
│   │       ├── _risk_card.html   # thẻ màu An toàn/Nghi ngờ/Nguy hiểm
│   │       ├── _detective.html
│   │       ├── _psychologist.html
│   │       ├── _rescue.html
│   │       └── _links_warning.html
│   └── static/
│       ├── css/
│       │   ├── tokens.css        # ⭐ foundation tokens (anti-ai-design đóng băng)
│       │   └── app.css           # Tailwind CDN + override >=18px, AA contrast
│       └── js/
│           ├── app.js            # nút Kiểm tra, fetch /check, render
│           ├── highlight-excerpts.js  # tô vàng <mark> theo excerpt
│           ├── history.js        # localStorage 10 tin gần nhất (L2-09)
│           ├── samples.js        # 3 nút tin mẫu (L2-06)
│           └── practice.js       # state máy luyện tập (Cấp 4-C)
├── data/                         # dữ liệu tĩnh (không qua AI)
│   ├── legit_domains.json        # Cấp 4-B: whitelist tên miền chính thống
│   ├── quiz.json                 # Cấp 4-C: 10 tin đã gán nhãn
│   └── hotlines.json             # Cấp 5: ≥10 ngân hàng + công an + Cục ATTT
├── tests/                        # pytest — MỌI hàm trong services/ đều có test
│   ├── conftest.py               # fixture: mock Gemini HTTP, app client
│   ├── test_gemini_client.py
│   ├── test_parser_detective.py
│   ├── test_parser_psychologist.py
│   ├── test_parser_rescuer.py
│   ├── test_activation_condition.py
│   ├── test_psychologist_chain.py
│   ├── test_validation.py
│   ├── test_links.py
│   ├── test_quiz.py
│   ├── test_hotlines_filter.py
│   └── test_routes.py
├── .env.example                  # mẫu env (KHÔNG có key thật)
├── .env                          # git-ignored, key thật (mentor cấp)
├── .gitignore
├── requirements.txt              # flask, requests, gunicorn, pytest...
├── pytest.ini
├── run.py                        # entrypoint dev: python run.py
├── scamcheck.service             # systemd unit (deploy)
├── README.md                     # N7-01
├── PLAN.md                       # ← file này bổ sung
└── ARCHITECTURE.md               # file này
```

---

## 3. Bố cục hàm (core functions)

### 3.1 `app/services/gemini.py` — client HTTP Gemini
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

### 3.2 `app/services/parser.py` — parse có dự phòng (L2-02)
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

### 3.3 `app/services/validation.py`
```python
MAX_LEN = 5000

def validate_input(text: str) -> list[str]:
    """ Trả danh sách lỗi thân thiện: rỗng, quá dài. """
```

### 3.4 `app/services/links.py` (Cấp 4-B)
```python
URL_RE = re.compile(...)  # bắt http(s), bit.ly, t.co ...

def extract_urls(text: str) -> list[str]: ...

def detect_spoofed_domains(urls: list[str],
                            whitelist: list[str]) -> list[Warning]: ...
```

### 3.5 `app/services/rescuer.py` (Cấp 5)
```python
def build_rescue_pipeline(situation: str, hotlines: list[Hotline]) -> RescueResult:
    """ 1) load hotlines.json → 2) gọi AI (chỉ số trong whitelist) → 3) post-filter """

def strip_unknown_phones(text: str, whitelist: set[str]) -> str:
    """ RÀNG BUỘC NGHIÊM: xoá mọi số không có trong whitelist. """
```

### 3.6 Routes
```python
# main.py
@bp.get("/")            → render home.html

# check.py
@bp.post("/check")
def check():
    errors = validate_input(text)
    if errors: return render(error)            # L2-08
    det = call_detective(text)                 # bọc try → fallback parser
    psy = call_psychologist(text) if det.risk in {nghi,nguy} else None  # L3-03
    return render(result.html, detective=det, psychologist=psy)

# rescue.py
@bp.post("/rescue")
def rescue():
    situation = request.json["situation"]      # 1 trong 4 lựa chọn
    if situation == "chua_lam_gi": return praise_msg()   # L5-05, không gọi AI
    result = build_rescue_pipeline(situation, load_hotlines())
    return render(result)
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

### 4.4 Dữ liệu tĩnh
- `data/hotlines.json`: `[{ "name": "Vietcombank", "phone": "1900545...", "type": "bank" }, ...]`
- `data/quiz.json`: `[{ "text": "...", "is_scam": true, "reason": "..." }, ...]` (10 mục)
- `data/legit_domains.json`: `{ "banks": ["vietcombank.com.vn", ...], "gov": [...] }`

---

## 5. Bảo mật & tuân thủ đề bài

1. **Khóa bí mật**: `GEMINI_API_KEY` chỉ đọc từ env/`.env` (`.env` trong `.gitignore`).
   Có pre-commit / CI check `git log -p | grep GEMINI_API_KEY` = rỗng. (L1-01, tiêu chí Cấp 1)
2. **Pháp lý**: `partials/_legal.html` nhúng trong `base.html` → **mọi màn hình** đều có. (L1-04)
3. **Cấp 5 — không AI tự sinh số**: `strip_unknown_phones()` post-filter mọi số điện thoại;
   chỉ số trong `data/hotlines.json` được giữ. (L5-03/L5-04)
4. **Không đăng nhập / không DB riêng**: lịch sử ở `localStorage`, đúng *Ngoài phạm vi* của đề.
5. **Đầu vào**: giới hạn ≤5000 ký tự + không rỗng, tránh lạm dụng token.

---

## 6. Tách tầng & kiểm thử

- **Routes** (Flask) chỉ lo HTTP + gọi service + render. Mỏng.
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
- Output: đóng băng **foundation tokens** → `app/static/css/tokens.css`
  (font-size ≥18px, spacing, màu risk, bo góc, shadow...).
- Bất kỳ CSS nào đều tham chiếu tokens, không hardcode → giữ nhất quán xuyên suốt.

### 7.2 utility-ui-eval (gate UX)
- Gate **chặn** ở **cuối mỗi Stage 2–5**.
- Orchestrator CHỈ: (a) chụp screenshot các state (home/loading/result/3 màu/empty/error/4 tình huống)
  ở viewport iPhone + desktop; (b) spawn **vision-capable subagent** với rubric 28-dimension;
  (c) **không tự chấm**, hành động theo verdict.
- Phải PASS §1–§15 (comprehension) VÀ §16–§28 (null-interaction / fake-functionality).
- Nếu BLOCKED (không có vision subagent) → báo rõ, không bịa điểm.

---

## 8. Triển khai (deploy)

- **Dev**: `python run.py` → `http://localhost:5000`.
- **Prod (VM deploy target):**
  - **VM:** `team6-scamcheck.exe.xyz`.
  - **Public proxy:** `https://team6-scamcheck.exe.xyz:8000/` (proxy xác thực user, forward vào service nội bộ).
  - Service chạy gunicorn trong VM ở port nội bộ (vd `:8000`/`:9595`), systemd unit `scamcheck.service`.
  - Reverse proxy công khai (đáp ứng L1-05).
  - Env `GEMINI_API_KEY` qua systemd `EnvironmentFile=/etc/scamcheck.env`.
- Tương đương Render/Railway trong đề bài; đảm bảo "không cài app phía người dùng".

> ⚠️ **Lưu ý:** VM deploy `team6-scamcheck.exe.xyz` **khác** VM dev hiện tại.
> Dev/scaffold/test chạy trên VM hiện tại; chỉ ship bản chạy được lên VM target.
