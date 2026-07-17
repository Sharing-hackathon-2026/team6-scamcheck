# ScamCheck

Công cụ web giúp người từ 45 tuổi trở lên kiểm tra nhanh tin nhắn nghi ngờ lừa đảo.
Hackathon FCT — Team 6. AI: Google Gemini.

## Kiến trúc (tách 2 phần)

| Phần | Thư mục | Công nghệ | Phục vụ bởi |
|---|---|---|---|
| **Frontend** | `frontend/` | HTML + CSS token hoá + JavaScript thuần | **Nginx** (static) |
| **Backend** | `backend/` | **Python Flask REST API** (JSON, không Jinja2) | **gunicorn** + systemd |

- Trình duyệt gọi `fetch('/api/...')` → Nginx reverse-proxy `/api/*` sang Flask → **cùng origin, không lo CORS**.
- `GEMINI_API_KEY` chỉ tồn tại ở backend.

## Deploy target

- **VM:** `team6-scamcheck.exe.xyz` (**khác** VM dev).
- **Public URL (SSL):** `https://team6-scamcheck.exe.xyz/`; lớp edge tự forward tới Nginx nội bộ ở port `8000`.
- Nginx phục vụ `frontend/` tại `/` + proxy `/api/*` → `127.0.0.1:5000` (Flask/gunicorn).
- Source: `https://hackathon-project.int.exe.xyz/Sharing-hackathon-2026/team6-scamcheck`

## Chạy trên máy cá nhân (dev)

### Yêu cầu
- Python 3.11+ và `pip`.
- Một khóa API Gemini (test local dùng `gemini-3.1-flash-lite`).

### Backend
```bash
cd backend
python -m venv .venv && . .venv/bin/activate   # lần đầu
pip install -r requirements.txt                  # lần đầu

# Tạo .env (KHÔNG commit):
cp ../.env.example ../.env
# rồi điền GEMINI_API_KEY=... vào ../.env

# Chạy (auto-nạp .env qua python-dotenv nếu có; hoặc export thủ công):
set -a && . ../.env && set +a && python run.py
# → http://localhost:5000/api/health
```

Chạy test:
```bash
cd backend && . .venv/bin/activate && pytest      # 193 test, dùng mock (không tốn lượt AI)
```

Chạy riêng bộ hồi quy 20 tin với Gemini thật (có tốn API):
```bash
cd backend && GEMINI_API_KEY=... python scripts/run_regression.py
```

Chạy báo cáo Stage 4 trên 60 tin (mặc định nghỉ 4,2 giây giữa calls để tôn trọng rate limit):
```bash
cd backend
GEMINI_API_KEY=... python scripts/run_stage4_evaluation.py \
  --prompt-mode stage3 --output-name baseline
GEMINI_API_KEY=... python scripts/run_stage4_evaluation.py \
  --prompt-mode stage4 --output-name improved
python scripts/combine_stage4_reports.py \
  reports/baseline.json reports/improved.json
```
Mỗi run tốn 60 calls; không chạy trong pytest/deploy. Report gần nhất nằm ở
`backend/reports/stage4-evaluation.{json,md}`.

### Frontend
Dev tách port: phục vụ `frontend/` ở `:5500`, trỏ tới backend `:5000`.
```bash
cd frontend
# Sửa assets/js/config.js: export const API_BASE = 'http://localhost:5000';
python -m http.server 5500
# → http://localhost:5500
```

Kiểm thử helper frontend (highlight, lịch sử, ứng cứu, chia sẻ, tùy chọn đọc):
```bash
npm --prefix frontend test       # 76 test Node, không cần runtime dependency ngoài
npm --prefix frontend run check  # syntax check toàn bộ JavaScript
```

Stage 2 bổ sung thẻ rủi ro, tô vàng excerpt an toàn XSS, lịch sử localStorage 10 mục,
3 tin mẫu, loading/error state, Web Speech API và giao diện ≥18px/touch target ≥44px.
Mọi text đi qua boundary API, textarea, speech và localStorage được chuẩn hoá Unicode NFC
(precomposed) để tiếng Việt render ổn định trên các trình duyệt cũ.
Stage 3 bổ sung terminal function-call handoff từ Thám tử sang Cô tâm lý, lỗi hai
phần độc lập, guardrail prompt injection, bộ hồi quy 20 tin và thư viện 12 kiểu
lừa đảo thuộc 4 nhóm với bộ lọc không reload.

Stage 4 bổ sung URL extraction/redirect resolver chống SSRF, phát hiện domain IDN/
homoglyph/lookalike, rule engine theo mệnh đề, cache hash TTL/LRU, bộ đánh giá 60 tin
và chế độ luyện tập 10 câu tại `/practice.html`. Báo cáo thật gần nhất: accuracy
`51,7% → 66,7%`, hard-case accuracy `53,6% → 71,4%`, danger recall giữ `100%`;
điểm yếu chính còn lại là phân biệt `nghi_ngo` với `nguy_hiem`.

Stage 5 bổ sung câu hỏi tình huống một chạm, FSM ba persona, Người ứng cứu có deterministic
fallback/kill switch, bảng 10 ngân hàng + Công an + kênh 156 có bằng chứng theo từng số và post-filter
cứng mọi số điện thoại. Kết quả có thể xuất ảnh PNG 1080×1350 với QR same-origin chuẩn,
Web Share/download fallback; high contrast và chữ 100%/115%/130% được lưu trên thiết bị.
Runbook crisis flow: `backend/RESCUE_RUNBOOK.md`.

Frontend hiện dùng kiến trúc một tác vụ mỗi trang: `/` kiểm tra, `/library.html` thư viện,
`/practice.html` luyện tập. Visual direction mint/forest/violet được đo từ Own Your Online
Scam Check và ghi tại `DESIGN_REFERENCE.md`, nhưng không sao chép logo/copy/asset độc quyền.
Be Vietnam Pro và Material Symbols Rounded được self-host kèm giấy phép; Galano Grotesque
không bị scrape/hotlink vì là font thương mại. Giao diện tự chuyển light/dark bằng
`prefers-color-scheme` của hệ điều hành; không có toggle theme thủ công. Fresh UX gate
`gpt-5.6-terra` + Browse CLI: main `8,6/10`, practice `8,0/10`, đều
`true_operational_tool`, không critical/major và khuyến nghị ship.
Stage 5 fresh safety mentor gate: PASS, không critical/major. Fresh UX gate 28 chiều:
`7,7/10`, `true_operational_tool`, không critical/major, khuyến nghị ship. Hai vòng safety
FAIL trước được giữ trong báo cáo để chứng minh các lỗi AI prose/113/QR Host/hotline source
đã được sửa. Bảng tự kiểm tiếp cận nằm tại `frontend/ACCESSIBILITY.md`.

(Sửa `config.js` chỉ khi dev tách port. Prod để rỗng vì Nginx cùng origin.)

## Deploy (đang chạy trên VM target)

- **🟢 LIVE:** https://team6-scamcheck.exe.xyz/
- `GET /api/health` → `{"ok":true,"ready":true}`
- `POST /api/check` → function-call Thám tử, chain Cô tâm lý khi cần, retry rate-limit; không giới hạn lượt theo phiên.
- `POST /api/rescue` → 4 situation enum, hotline whitelist + guarded fallback; `GET /api/share/qr.svg` không nhận URL tùy ý.

Deploy idempotent qua `deploy/deploy.sh` (chạy **trên VM target**, cần sudo):
```bash
# trên VM target:
ssh exedev@team6-scamcheck.exe.xyz
# đã có /etc/scamcheck.env (chứa GEMINI_API_KEY, root:exedev 640)
git clone https://hackathon-project.int.exe.xyz/Sharing-hackathon-2026/team6-scamcheck.git /tmp/d
bash /tmp/d/deploy/deploy.sh && rm -rf /tmp/d
```
Script tự: clone vào `/opt/scamcheck` → tạo venv → chạy pytest (phải xanh) → cài systemd
`scamcheck-backend` (gunicorn :5000) + nginx (frontend/ + `/api/*` proxy). Chạy lại = update.

## Tài liệu

- Kế hoạch triển khai theo cấp: [`PLAN.md`](PLAN.md)
- Cấu trúc thư mục + sơ đồ luồng dữ liệu: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Visual reference, số đo và quyết định licence: [`DESIGN_REFERENCE.md`](DESIGN_REFERENCE.md)
- Hợp đồng API: [`API.md`](API.md)

